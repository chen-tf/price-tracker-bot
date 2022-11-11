from lotify.client import Client

import pt_config

client = Client(
    client_id=pt_config.LINE_NOTIFY_CLIENT_ID,
    client_secret=pt_config.LINE_NOTIFY_CLIENT_SECRET,
    redirect_uri=pt_config.LINE_NOTIFY_REDIRECT_URL
)


def get_lotify_client():
    return client
