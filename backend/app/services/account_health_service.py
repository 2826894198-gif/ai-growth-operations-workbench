"""Read-only account health evaluation for the detection center.

The evaluator deliberately keeps connection, data, performance and content
states separate.  It reads persisted provider/sync state only and never calls a
provider or performs a provider mutation.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.review import AccountDetectionSetting, AccountHealthEvent
from app.models.social import ConnectedAccount, ProviderConnection
from app.services.data_health_service import DataHealthService, _ensure_aware

STATUS_RANK = {"HEALTHY": 0, "UNKNOWN": 1, "WARNING": 2, "AT_RISK": 3, "CRITICAL": 4}
DEFAULT_DETECTION_RULES = {
    "sync_delay_minutes": 20,
    "sync_stale_minutes": 60,
    "content_inactive_days": 7,
}


def _worst(*values: str) -> str:
    return max(values, key=lambda value: STATUS_RANK.get(value, STATUS_RANK["UNKNOWN"]))


def _connection_status(account: ConnectedAccount, connection: Optional[ProviderConnection]) -> tuple[str, List[Dict[str, Any]]]:
    if account.status in {"DISCONNECTED", "EXPIRED"}:
        return "CRITICAL", [
            {
                "rule_code": "ACCOUNT_DISCONNECTED",
                "severity": "CRITICAL",
                "title": "账号已断开",
                "detail": "账号状态不是 LINKED，需要重新连接后才能继续同步。",
                "observed_value": account.status,
                "action": "前往连接与设置重新授权",
            }
        ]
    if connection is None:
        return "UNKNOWN", [
            {
                "rule_code": "CONNECTION_UNKNOWN",
                "severity": "WARNING",
                "title": "无法确认连接状态",
                "detail": "账号没有可追溯的 ProviderConnection。",
                "observed_value": None,
                "action": "检查账号与连接的映射",
            }
        ]

    mapping = {
        "HEALTHY": ("HEALTHY", None),
        "EXPIRING": ("WARNING", "TOKEN_EXPIRING"),
        "REAUTH_REQUIRED": ("CRITICAL", "CONNECTION_REAUTH_REQUIRED"),
        "SCOPE_MISSING": ("AT_RISK", "SCOPE_MISSING"),
        "RATE_LIMITED": ("WARNING", "RATE_LIMITED"),
        "WEBHOOK_FAILED": ("WARNING", "WEBHOOK_FAILED"),
        "DISABLED": ("CRITICAL", "CONNECTION_DISABLED"),
        "UNKNOWN": ("UNKNOWN", "CONNECTION_UNKNOWN"),
    }
    state, rule = mapping.get((connection.status or "UNKNOWN").upper(), ("UNKNOWN", "CONNECTION_UNKNOWN"))
    if rule is None:
        return state, []
    titles = {
        "TOKEN_EXPIRING": "授权即将过期",
        "CONNECTION_REAUTH_REQUIRED": "连接需要重新授权",
        "SCOPE_MISSING": "缺少读取权限",
        "RATE_LIMITED": "Provider 正在限流",
        "WEBHOOK_FAILED": "Webhook 状态异常",
        "CONNECTION_DISABLED": "连接已停用",
        "CONNECTION_UNKNOWN": "连接状态未知",
    }
    return state, [
        {
            "rule_code": rule,
            "severity": state if state != "UNKNOWN" else "WARNING",
            "title": titles[rule],
            "detail": f"Provider 连接状态为 {connection.status or 'UNKNOWN'}。",
            "observed_value": connection.status,
            "action": "前往连接与设置检查授权与权限范围",
        }
    ]


def _data_status(
    account: ConnectedAccount,
    now: datetime,
    rules: Dict[str, int],
) -> tuple[str, Optional[datetime], List[Dict[str, Any]]]:
    sync_values = [
        _ensure_aware(value)
        for value in (account.last_profile_sync_at, account.last_content_sync_at, account.last_analytics_sync_at)
        if value is not None
    ]
    last_sync = max(sync_values) if sync_values else None
    if last_sync is None:
        return "UNKNOWN", None, [
            {
                "rule_code": "SYNC_NEVER_SUCCEEDED",
                "severity": "AT_RISK",
                "title": "尚未记录成功同步",
                "detail": "账号缺少 profile、content 和 analytics 的成功同步时间。",
                "observed_value": None,
                "action": "检查同步任务并完成首次同步",
            }
        ]

    lag_minutes = max(0.0, (now - last_sync).total_seconds() / 60)
    if lag_minutes <= rules["sync_delay_minutes"]:
        return "HEALTHY", last_sync, []
    if lag_minutes <= rules["sync_stale_minutes"]:
        return "WARNING", last_sync, [
            {
                "rule_code": "DATA_DELAYED",
                "severity": "WARNING",
                "title": "账号数据同步延迟",
                "detail": f"最近成功同步距今 {round(lag_minutes)} 分钟。",
                "observed_value": round(lag_minutes, 1),
                "action": "观察下一次同步任务",
            }
        ]
    return "AT_RISK", last_sync, [
        {
            "rule_code": "DATA_STALE",
            "severity": "AT_RISK",
            "title": "账号数据已过期",
            "detail": f"最近成功同步距今 {round(lag_minutes)} 分钟，当前经营结论应降级。",
            "observed_value": round(lag_minutes, 1),
            "action": "检查连接、同步任务和数据源状态",
        }
    ]


def _performance_status(account: ConnectedAccount) -> tuple[str, List[Dict[str, Any]]]:
    raw = (account.health_status or "UNKNOWN").upper()
    mapping = {
        "HEALTHY": "HEALTHY",
        "DEGRADED": "WARNING",
        "WARNING": "WARNING",
        "AT_RISK": "AT_RISK",
        "DISCONNECTED": "CRITICAL",
        "CRITICAL": "CRITICAL",
        "UNKNOWN": "UNKNOWN",
    }
    state = mapping.get(raw, "UNKNOWN")
    if state in {"HEALTHY", "UNKNOWN"}:
        return state, []
    return state, [
        {
            "rule_code": "ACCOUNT_PERFORMANCE_STATUS",
            "severity": state,
            "title": "账号经营表现需要关注",
            "detail": f"当前账号表现状态为 {raw}。",
            "observed_value": raw,
            "action": "进入账号复盘查看指标驱动",
        }
    ]


def _content_status(
    account: ConnectedAccount,
    now: datetime,
    rules: Dict[str, int],
) -> tuple[str, List[Dict[str, Any]]]:
    last_content = _ensure_aware(account.last_content_sync_at)
    if last_content is None:
        return "UNKNOWN", []
    days = (now - last_content).total_seconds() / 86400
    if days <= rules["content_inactive_days"]:
        return "HEALTHY", []
    return "WARNING", [
        {
            "rule_code": "CONTENT_INACTIVE",
            "severity": "WARNING",
            "title": "内容活跃度需要确认",
            "detail": f"最近内容同步距今 {round(days, 1)} 天。",
            "observed_value": round(days, 1),
            "action": "确认是否为计划内停更或同步缺失",
        }
    ]


async def evaluate_account(
    db: AsyncSession,
    account: ConnectedAccount,
    *,
    now: Optional[datetime] = None,
    rules: Optional[Dict[str, int]] = None,
) -> Dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    rules = rules or DEFAULT_DETECTION_RULES
    connection = None
    if account.connection_id:
        connection = (
            await db.execute(
                select(ProviderConnection).where(
                    ProviderConnection.id == account.connection_id,
                    ProviderConnection.workspace_id == account.workspace_id,
                )
            )
        ).scalar_one_or_none()

    connection_state, connection_events = _connection_status(account, connection)
    data_state, last_sync, data_events = _data_status(account, now, rules)
    performance_state, performance_events = _performance_status(account)
    content_state, content_events = _content_status(account, now, rules)
    overall = _worst(connection_state, data_state, performance_state, content_state)
    data_usable = connection_state not in {"CRITICAL"} and data_state in {"HEALTHY", "WARNING"}

    events = connection_events + data_events + performance_events + content_events
    for event in events:
        event["id"] = f"{account.id}:{event['rule_code']}"
        event["account_id"] = str(account.id)
        event["username"] = account.username
        event["platform"] = account.platform
        event["detected_at"] = now.isoformat()
        event["workflow_status"] = "OPEN"
        event["owner_id"] = None

    return {
        "account_id": str(account.id),
        "workspace_id": account.workspace_id,
        "username": account.username,
        "display_name": account.display_name,
        "provider": account.provider,
        "platform": account.platform,
        "account_type": account.account_type,
        "is_test": account.is_test,
        "statuses": {
            "connection": connection_state,
            "data": data_state,
            "performance": performance_state,
            "content": content_state,
            "overall": overall,
        },
        "data_usable": data_usable,
        "last_sync_at": last_sync.isoformat() if last_sync else None,
        "connection": {
            "id": str(connection.id) if connection else None,
            "provider_status": connection.status if connection else "UNKNOWN",
            "token_expires_at": connection.token_expires_at.isoformat() if connection and connection.token_expires_at else None,
            "last_validated_at": connection.last_validated_at.isoformat() if connection and connection.last_validated_at else None,
            "authorized_scopes": connection.authorized_scopes if connection else None,
        },
        "events": events,
        "evaluated_at": now.isoformat(),
        "rule_version": "v1",
        "detection_rules": rules,
    }


async def get_detection_rules(db: AsyncSession, workspace_id: str) -> Dict[str, int]:
    row = (
        await db.execute(
            select(AccountDetectionSetting).where(
                AccountDetectionSetting.workspace_id == workspace_id
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return dict(DEFAULT_DETECTION_RULES)
    return {
        "sync_delay_minutes": row.sync_delay_minutes,
        "sync_stale_minutes": row.sync_stale_minutes,
        "content_inactive_days": row.content_inactive_days,
    }


async def _overlay_event_workflow(
    db: AsyncSession,
    *,
    workspace_id: str,
    rows: List[Dict[str, Any]],
) -> None:
    records = list(
        (
            await db.execute(
                select(AccountHealthEvent)
                .where(AccountHealthEvent.workspace_id == workspace_id)
                .order_by(AccountHealthEvent.created_at.desc())
            )
        ).scalars().all()
    )
    latest: Dict[tuple[str, str], AccountHealthEvent] = {}
    for record in records:
        latest.setdefault((record.account_id, record.rule_code), record)
    for row in rows:
        for event in row["events"]:
            record = latest.get((event["account_id"], event["rule_code"]))
            if record is None:
                continue
            event.update(
                {
                    "record_id": str(record.id),
                    "workflow_status": record.status,
                    "owner_id": record.owner_id,
                    "acknowledged_at": (
                        record.acknowledged_at.isoformat()
                        if record.acknowledged_at
                        else None
                    ),
                    "resolved_at": (
                        record.resolved_at.isoformat() if record.resolved_at else None
                    ),
                }
            )


def _event_record_payload(record: AccountHealthEvent) -> Dict[str, Any]:
    return {
        "record_id": str(record.id),
        "workspace_id": record.workspace_id,
        "account_id": record.account_id,
        "rule_code": record.rule_code,
        "severity": record.severity,
        "workflow_status": record.status,
        "owner_id": record.owner_id,
        "acknowledged_at": (
            record.acknowledged_at.isoformat() if record.acknowledged_at else None
        ),
        "resolved_at": record.resolved_at.isoformat() if record.resolved_at else None,
    }


async def update_event_workflow(
    db: AsyncSession,
    *,
    workspace_id: str,
    account_id: str,
    rule_code: str,
    status: str,
    owner_id: Optional[str],
) -> Optional[Dict[str, Any]]:
    detail = await account_health_detail(
        db,
        workspace_id=workspace_id,
        account_id=account_id,
    )
    if detail is None:
        return None
    event = next(
        (item for item in detail["events"] if item["rule_code"] == rule_code),
        None,
    )
    if event is None:
        return None
    record = (
        await db.execute(
            select(AccountHealthEvent)
            .where(
                AccountHealthEvent.workspace_id == workspace_id,
                AccountHealthEvent.account_id == account_id,
                AccountHealthEvent.rule_code == rule_code,
            )
            .order_by(AccountHealthEvent.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if record is None:
        record = AccountHealthEvent(
            workspace_id=workspace_id,
            account_id=account_id,
            rule_code=rule_code,
            rule_version="v1",
            severity=event["severity"],
            detected_at=now,
            observed_value=(
                str(event["observed_value"])
                if event.get("observed_value") is not None
                else None
            ),
            evidence={
                "title": event["title"],
                "detail": event["detail"],
                "action": event["action"],
            },
        )
        db.add(record)
    record.status = status
    record.owner_id = owner_id or record.owner_id
    if status == "OPEN":
        record.acknowledged_at = None
        record.resolved_at = None
    elif status == "IN_PROGRESS":
        record.acknowledged_at = record.acknowledged_at or now
        record.resolved_at = None
    else:
        record.acknowledged_at = record.acknowledged_at or now
        record.resolved_at = now
    await db.flush()
    return _event_record_payload(record)


async def account_health_detail(db: AsyncSession, *, workspace_id: str, account_id: str) -> Optional[Dict[str, Any]]:
    account = (
        await db.execute(
            select(ConnectedAccount).where(
                ConnectedAccount.id == account_id,
                ConnectedAccount.workspace_id == workspace_id,
            )
        )
    ).scalar_one_or_none()
    if account is None:
        return None
    rules = await get_detection_rules(db, workspace_id)
    result = await evaluate_account(db, account, rules=rules)
    await _overlay_event_workflow(db, workspace_id=workspace_id, rows=[result])
    return result


async def health_summary(db: AsyncSession, *, workspace_id: str) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    rules = await get_detection_rules(db, workspace_id)
    accounts = list(
        (
            await db.execute(
                select(ConnectedAccount)
                .where(ConnectedAccount.workspace_id == workspace_id)
                .order_by(ConnectedAccount.created_at.asc())
            )
        ).scalars().all()
    )
    rows = [
        await evaluate_account(db, account, now=now, rules=rules)
        for account in accounts
    ]
    await _overlay_event_workflow(db, workspace_id=workspace_id, rows=rows)
    counts = {key.lower(): 0 for key in STATUS_RANK}
    for row in rows:
        counts[row["statuses"]["overall"].lower()] += 1

    events = sorted(
        [event for row in rows for event in row["events"]],
        key=lambda item: STATUS_RANK.get(str(item["severity"]), 1),
        reverse=True,
    )
    workflow_counts = {
        status: sum(
            1 for event in events if event.get("workflow_status", "OPEN") == status
        )
        for status in ("OPEN", "IN_PROGRESS", "RESOLVED", "IGNORED")
    }
    freshness = await DataHealthService().freshness(db, workspace_id=workspace_id)
    source_blocked = any(source["status"] in {"STALE", "UNKNOWN"} for source in freshness)
    data_usable = bool(rows) and all(row["data_usable"] for row in rows) and not source_blocked

    blocking_reasons = list(
        dict.fromkeys(
            event["rule_code"]
            for event in events
            if event["severity"] in {"CRITICAL", "AT_RISK"}
        )
    )
    return {
        "workspace_id": workspace_id,
        "evaluated_at": now.isoformat(),
        "environment": settings.app_env,
        "data_mode": settings.data_provider_mode.upper(),
        "write_mode": "DISABLED" if not settings.meta_write_enabled and not settings.google_ads_write_enabled else "RESTRICTED",
        "counts": {"total_accounts": len(rows), **counts},
        "data_usable": data_usable,
        "blocking_reasons": blocking_reasons[:5],
        "top_events": events[:12],
        "workflow_counts": workflow_counts,
        "accounts": rows,
        "sources": freshness,
        "detection_rules": rules,
        "caveats": [
            "连接、数据、经营与内容状态独立计算；总状态仅用于排序。",
            "经营状态沿用已入库的账号表现结果，不会在页面请求时调用 Provider。",
        ],
    }
