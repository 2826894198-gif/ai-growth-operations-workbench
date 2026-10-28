from typing import Dict


class GAQLQueryBuilder:
    """Central GAQL query builder - no query strings scattered in services."""

    COMMON_METRICS = (
        "metrics.impressions,metrics.clicks,metrics.cost_micros,"
        "metrics.conversions,metrics.conversions_value"
    )

    def campaign_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, campaign.name, campaign.status, campaign.start_date, campaign.end_date, "
            "campaign.advertising_channel_type, campaign.advertising_channel_sub_type, "
            "segments.date, "
            + self.COMMON_METRICS
            + f" FROM campaign WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        )

    def ad_group_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status, segments.date, "
            + self.COMMON_METRICS
            + f" FROM ad_group WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        )

    def ad_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, ad_group.id, ad.id, ad.status, segments.date, "
            + self.COMMON_METRICS
            + f" FROM ad WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        )

    def keyword_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, ad_group.id, ad_group_criterion.criterion_id, "
            "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type, segments.date, "
            + self.COMMON_METRICS
            + f" FROM keyword_view WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        )

    def search_term_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, ad_group.id, search_term_view.search_term, segments.date, "
            + self.COMMON_METRICS
            + f" FROM search_term_view WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        )

    def conversion_action_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, ad_group.id, segments.conversion_action, segments.date, "
            "metrics.conversions, metrics.conversions_value "
            f"FROM campaign WHERE segments.date BETWEEN '{start_date}' AND '{end_date}' "
            "AND segments.conversion_action IS NOT NULL"
        )

    def asset_group_daily(self, start_date: str, end_date: str) -> str:
        return (
            "SELECT campaign.id, asset_group.id, asset_group.name, asset_group.status, segments.date, "
            + self.COMMON_METRICS
            + f" FROM asset_group WHERE segments.date BETWEEN '{start_date}' AND '{end_date}'"
        )

    def dimensions(self) -> Dict[str, str]:
        return {
            "campaigns": (
                "SELECT campaign.id, campaign.name, campaign.status, campaign.start_date, campaign.end_date, "
                "campaign.advertising_channel_type, campaign.advertising_channel_sub_type FROM campaign"
            ),
            "ad_groups": "SELECT campaign.id, ad_group.id, ad_group.name, ad_group.status, ad_group.type FROM ad_group",
            "ads": "SELECT campaign.id, ad_group.id, ad.id, ad.status FROM ad",
            "keywords": (
                "SELECT campaign.id, ad_group.id, ad_group_criterion.criterion_id, "
                "ad_group_criterion.keyword.text, ad_group_criterion.keyword.match_type FROM keyword_view"
            ),
            "asset_groups": "SELECT campaign.id, asset_group.id, asset_group.name, asset_group.status FROM asset_group",
            "conversion_actions": "SELECT conversion_action.id, conversion_action.name FROM conversion_action",
        }
