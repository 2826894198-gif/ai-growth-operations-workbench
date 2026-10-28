import logging
from typing import Any, Dict, List, Optional

import yaml

from app.core.project_paths import config_path
from app.models.rules import RuleDefinition, RuleParameter

logger = logging.getLogger(__name__)

RULES_CONFIG_DIR = config_path("rules")
PACK_FILES = [
    "core_safety.yaml",
    "meta_performance.yaml",
    "google_search.yaml",
    "funnel.yaml",
    "commerce.yaml",
    "cross_channel.yaml",
]


def load_defaults() -> Dict[str, Any]:
    path = RULES_CONFIG_DIR / "defaults.yaml"
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def load_rule_packs(include_disabled: bool = False) -> List[Dict[str, Any]]:
    defaults = load_defaults()
    packs = defaults.get("rule_packs", {})
    rules: List[Dict[str, Any]] = []
    for filename in PACK_FILES:
        pack_name = filename.replace(".yaml", "")
        if not include_disabled and not packs.get(pack_name, True):
            continue
        path = RULES_CONFIG_DIR / filename
        if not path.exists():
            continue
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for rule in data.get("rules", []):
            rule["pack"] = pack_name
            rules.append(rule)
    return rules


def get_seed_parameters(rule_key: str, defaults: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    defaults = defaults or load_defaults()
    platform_params: Dict[str, Any] = {}
    if rule_key.startswith("META") or rule_key.startswith("FUNNEL"):
        platform_params = defaults.get("meta", {})
    elif rule_key.startswith("GOOGLE"):
        platform_params = defaults.get("google", {})
    elif rule_key.startswith("COM") or rule_key.startswith("XC"):
        platform_params = defaults.get("commerce", {})
    for section in platform_params.values():
        if isinstance(section, dict) and rule_key.lower().endswith(section.get("_rule", "")):
            pass
    # Map rule_key suffix to parameter group.
    suffix_map = {
        "META_NO_PURCHASE_BURN": ("meta", "no_purchase_burn"),
        "META_CPA_OVERSHOOT": ("meta", "cpa_overshoot"),
        "META_SCALE_CANDIDATE": ("meta", "scale_candidate"),
        "META_CREATIVE_FATIGUE": ("meta", "creative_fatigue"),
        "META_LOW_CTR": ("meta", "low_ctr"),
        "META_CPM_SHOCK": ("meta", "cpm_shock"),
        "META_DELIVERY_COLLAPSE": ("meta", "delivery_collapse"),
        "META_AUDIENCE_SATURATION": ("meta", "audience_saturation"),
        "GOOGLE_NO_CONVERSION_BURN": ("google", "no_conversion_burn"),
        "GOOGLE_CPA_OVERSHOOT": ("google", "cpa_overshoot"),
        "GOOGLE_SEARCH_TERM_WASTE": ("google", "search_term_waste"),
        "GOOGLE_KEYWORD_WASTE": ("google", "keyword_waste"),
        "GOOGLE_CPC_SHOCK": ("google", "cpc_shock"),
        "GOOGLE_CTR_WEAKNESS": ("google", "ctr_weakness"),
    }
    group = suffix_map.get(rule_key)
    if group:
        section = defaults.get(group[0], {}).get(group[1], {})
        return dict(section)
    return {}


async def load_rules_from_db(db, include_packs: bool = True) -> List[Dict[str, Any]]:
    """Return effective rule configs: DB definitions override YAML seeds."""
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(RuleDefinition).order_by(RuleDefinition.rule_key, RuleDefinition.version.desc())
        )
    ).scalars().all()
    latest: Dict[str, RuleDefinition] = {}
    for row in rows:
        if row.rule_key not in latest:
            latest[row.rule_key] = row
    effective: List[Dict[str, Any]] = []
    yaml_rules = load_rule_packs() if include_packs else []
    seen: set = set()
    for rule in yaml_rules:
        seen.add(rule["rule_key"])
        db_rule = latest.get(rule["rule_key"])
        if db_rule is not None:
            rule = _db_rule_to_dict(db_rule)
        effective.append(rule)
    for key, db_rule in latest.items():
        if key not in seen:
            effective.append(_db_rule_to_dict(db_rule))
    return effective


def _db_rule_to_dict(rule: RuleDefinition) -> Dict[str, Any]:
    return {
        "rule_key": rule.rule_key,
        "name": rule.name,
        "category": rule.category,
        "platform": rule.platform,
        "evaluation_level": rule.evaluation_level,
        "severity": rule.severity,
        "schedule_group": rule.schedule_group,
        "conditions": rule.conditions or {},
        "guards": rule.guards or {},
        "action": rule.action_template or {},
        "required_capabilities": rule.required_capabilities or [],
        "cooldown_minutes": rule.cooldown_minutes,
        "minimum_confidence": rule.minimum_confidence,
        "auto_execution_eligible": rule.auto_execution_eligible,
        "status": rule.status,
        "enabled": rule.enabled,
        "version": rule.version,
    }


async def get_rule_parameters(db, rule_key: str, scope_type: str = "GLOBAL", scope_id: Optional[str] = None) -> Dict[str, Any]:
    """Scoped parameter resolution: campaign > account > platform > global."""
    from sqlalchemy import select

    rows = (
        await db.execute(
            select(RuleParameter).where(
                RuleParameter.rule_key == rule_key,
                RuleParameter.valid_to.is_(None),
            )
        )
    ).scalars().all()
    result: Dict[str, Any] = {}
    priority = {"GLOBAL": 0, "PLATFORM": 1, "ACCOUNT": 2, "CAMPAIGN": 3}
    ordered = sorted(rows, key=lambda r: priority.get(r.scope_type, 0))
    for row in ordered:
        if row.scope_type == "GLOBAL":
            result[row.parameter_key] = row.value
        elif row.scope_type == "PLATFORM" or (row.scope_type == "ACCOUNT" and row.scope_id == scope_id) or (row.scope_type == "CAMPAIGN" and row.scope_id == scope_id):
            result[row.parameter_key] = row.value
    return result
