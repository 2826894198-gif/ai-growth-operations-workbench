from app.core.config import settings


def get_social_provider(platform: str):
    platform = platform.upper()
    if settings.social_provider_mode == "mock":
        from app.integrations.social.mock import MockSocialProvider

        return MockSocialProvider(platform=platform)
    if platform == "INSTAGRAM" or platform == "FACEBOOK":
        from app.integrations.social.meta_instagram import MetaInstagramProvider

        return MetaInstagramProvider()
    if platform == "TIKTOK":
        from app.integrations.social.tiktok import TikTokProvider

        return TikTokProvider()
    if platform == "YOUTUBE":
        from app.integrations.social.youtube import YouTubeProvider

        return YouTubeProvider()
    raise ValueError(f"unknown social platform: {platform}")
