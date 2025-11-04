BASE_URL = "https://sysprosystembackend-develop-hybyc7adhkh4cgfy.eastus-01.azurewebsites.net/"
RECORDS_ENDPOINT = "/api/v1/Transactions"

def get_auth_headers(token: str):
    """
    Dynamically generate request headers with the user's Bearer token.

    Args:
        token (str): User's authentication token from the frontend

    Returns:
        dict: Authorization header dictionary
    """
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
