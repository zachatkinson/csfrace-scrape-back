"""Example: Adding new OAuth providers without modifying existing code.

This demonstrates the Open/Closed Principle - the system is open for extension
but closed for modification. New providers can be added without touching
the core OAuth service or factory code.
"""

from .models import OAuthProvider, OAuthUserInfo
from .oauth_service import OAuthProviderInterface


# Example: Adding a new Discord OAuth provider
class DiscordOAuthProvider(OAuthProviderInterface):
    """Discord OAuth provider implementation - extends without modifying existing code."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        self.authorization_url = "https://discord.com/api/oauth2/authorize"
        self.token_url = "https://discord.com/api/oauth2/token"  # noqa: S105
        self.user_info_url = "https://discord.com/api/users/@me"

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Discord authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": "identify email",
            "state": state,
        }
        from urllib.parse import urlencode

        return f"{self.authorization_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange code for Discord access token."""
        # Implementation would go here
        return "discord_access_token_example"

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch Discord user information."""
        # Implementation would go here
        return OAuthUserInfo(
            provider=OAuthProvider.DISCORD if hasattr(OAuthProvider, "DISCORD") else None,
            provider_id="discord_user_123",
            email="user@example.com",
            name="Discord User",
            avatar_url="https://cdn.discordapp.com/avatars/123/avatar.png",
        )


# Register the new provider (Open/Closed Principle in action!)
def register_discord_provider(client_id: str, client_secret: str) -> None:
    """Register Discord OAuth provider - no modification to existing code needed!"""
    # Note: This would require adding DISCORD to the OAuthProvider enum first
    # OAuthProviderRegistry.register_provider(
    #     OAuthProvider.DISCORD,
    #     DiscordOAuthProvider,
    #     client_id,
    #     client_secret
    # )
    pass  # Placeholder until OAuthProvider.DISCORD is added


# Example: Adding Twitter/X OAuth provider
class TwitterOAuthProvider(OAuthProviderInterface):
    """Twitter OAuth provider - another extension example."""

    def __init__(self, client_id: str, client_secret: str):
        self.client_id = client_id
        self.client_secret = client_secret
        # Twitter OAuth 2.0 endpoints
        self.authorization_url = "https://twitter.com/i/oauth2/authorize"
        self.token_url = "https://api.twitter.com/2/oauth2/token"  # noqa: S105
        self.user_info_url = "https://api.twitter.com/2/users/me"

    def get_authorization_url(self, state: str, redirect_uri: str) -> str:
        """Generate Twitter authorization URL."""
        # Implementation here
        return f"{self.authorization_url}?..."

    async def exchange_code_for_token(self, code: str, redirect_uri: str) -> str:
        """Exchange code for Twitter access token."""
        return "twitter_access_token_example"

    async def get_user_info(self, access_token: str) -> OAuthUserInfo:
        """Fetch Twitter user information."""
        return OAuthUserInfo(
            provider=OAuthProvider.TWITTER if hasattr(OAuthProvider, "TWITTER") else None,
            provider_id="twitter_user_123",
            email="user@twitter.com",
            name="Twitter User",
            avatar_url="https://pbs.twimg.com/profile_images/123/avatar.jpg",
        )


"""
Benefits of the Registry Pattern:

✅ Open/Closed Principle Compliance:
   - Open for extension: New providers can be added easily
   - Closed for modification: No need to modify existing OAuth code

✅ Single Responsibility Principle:
   - Each provider handles only its own OAuth implementation
   - Registry only handles provider registration and creation

✅ Dependency Inversion Principle:
   - Depends on OAuthProviderInterface abstraction
   - Core service doesn't depend on concrete provider implementations

To add a new provider:
1. Create provider class implementing OAuthProviderInterface
2. Add provider type to OAuthProvider enum
3. Register with OAuthProviderRegistry.register_provider()
4. Done! No modifications to existing code required.
"""
