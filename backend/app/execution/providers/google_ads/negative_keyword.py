"""Google negative keyword create/remove + scope + PMax validation
(PART 06 §76-§84, N-O)."""

from typing import Any, Dict

from app.execution.errors import ExecutionError, ExecutionErrorCode
from app.execution.providers.google_ads.client import GoogleWriteClient


def validate_negative_keyword_capability(campaign_type: str, match_type: str, scope: str) -> None:
    """PMax campaign-level negatives require explicit capability validation."""
    if campaign_type and campaign_type.upper() == "PERFORMANCE_MAX":
        if scope.upper() not in ("CAMPAIGN", "PMAX_CAMPAIGN"):
            raise ExecutionError(
                ExecutionErrorCode.ACTION_NOT_ALLOWED.value,
                f"PMax negative keywords must use CAMPAIGN scope, got {scope}",
            )
        if match_type.upper() not in ("EXACT", "PHRASE"):
            raise ExecutionError(
                ExecutionErrorCode.ACTION_NOT_ALLOWED.value,
                f"PMax negative keywords support EXACT/PHRASE only, got {match_type}",
            )
    elif scope.upper() not in ("AD_GROUP", "CAMPAIGN", "SHARED_SET", "ACCOUNT"):
        raise ExecutionError(
            ExecutionErrorCode.ACTION_NOT_ALLOWED.value,
            f"invalid negative keyword scope: {scope}",
        )


async def add_negative_keyword(
    client: GoogleWriteClient,
    *,
    keyword_text: str,
    match_type: str,
    scope: str,
    target_resource: str,
    campaign_id: str,
    campaign_type: str,
    validate_only: bool = False,
) -> Dict[str, Any]:
    validate_negative_keyword_capability(campaign_type, match_type, scope)
    keyword = client.get_type("Keyword")
    keyword.text = keyword_text
    keyword.match_type = client.get_type("KeywordMatchTypeEnum").KeywordMatchType.Value(match_type.upper())
    criterion = client.get_type("Criterion")
    criterion.keyword = keyword
    criterion.negative = True
    scope_upper = scope.upper()
    if scope_upper in ("AD_GROUP",):
        service = client.service("AdGroupCriterionService")
        operation = client.get_type("AdGroupCriterionOperation")
        ad_group_criterion = client.get_type("AdGroupCriterion")
        ad_group_criterion.ad_group = target_resource if target_resource.startswith("customers/") else (
            f"customers/{client.customer_id()}/adGroups/{target_resource}"
        )
        ad_group_criterion.criterion = criterion
        operation.create = ad_group_criterion
        request = client.get_type("MutateAdGroupCriteriaRequest")
        request.customer_id = client.customer_id()
        request.operations.append(operation)
        request.validate_only = validate_only
        request.partial_failure = False
        response = service.mutate_ad_group_criteria(request)
        resource_name = response.results[0].resource_name if response.results else None
    else:
        service = client.service("CampaignCriterionService")
        operation = client.get_type("CampaignCriterionOperation")
        campaign_criterion = client.get_type("CampaignCriterion")
        campaign_criterion.campaign = f"customers/{client.customer_id()}/campaigns/{campaign_id}"
        campaign_criterion.criterion = criterion
        operation.create = campaign_criterion
        request = client.get_type("MutateCampaignCriteriaRequest")
        request.customer_id = client.customer_id()
        request.operations.append(operation)
        request.validate_only = validate_only
        request.partial_failure = False
        response = service.mutate_campaign_criteria(request)
        resource_name = response.results[0].resource_name if response.results else None
    return {
        "resource_name": resource_name,
        "keyword_text": keyword_text,
        "match_type": match_type,
        "scope": scope,
        "validate_only": validate_only,
    }


async def remove_system_negative_keyword(client: GoogleWriteClient, resource_name: str, validate_only: bool = False) -> Dict[str, Any]:
    """Remove ONLY the exact resource created by this execution (PART 06 §84)."""
    if not resource_name or not resource_name.startswith("customers/"):
        raise ExecutionError(
            ExecutionErrorCode.PRECONDITION_FAILED.value,
            "provider_resource_name is required and must be a resource name",
        )
    if "/adGroupCriteria/" in resource_name:
        service = client.service("AdGroupCriterionService")
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = client.get_type("AdGroupCriterion")
        criterion.resource_name = resource_name
        operation.remove = criterion.resource_name
        request = client.get_type("MutateAdGroupCriteriaRequest")
        request.customer_id = client.customer_id()
        request.operations.append(operation)
        request.validate_only = validate_only
        request.partial_failure = False
        service.mutate_ad_group_criteria(request)
    else:
        service = client.service("CampaignCriterionService")
        operation = client.get_type("CampaignCriterionOperation")
        criterion = client.get_type("CampaignCriterion")
        criterion.resource_name = resource_name
        operation.remove = criterion.resource_name
        request = client.get_type("MutateCampaignCriteriaRequest")
        request.customer_id = client.customer_id()
        request.operations.append(operation)
        request.validate_only = validate_only
        request.partial_failure = False
        service.mutate_campaign_criteria(request)
    return {"removed": True, "validate_only": validate_only, "resource_name": resource_name}
