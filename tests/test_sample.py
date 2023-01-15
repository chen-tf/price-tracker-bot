# step1. arrange
from lotify_client import get_lotify_client


def test_sample():

    # step2. act
    lotify_client = get_lotify_client()

    # step3. assert
    assert isinstance(lotify_client, object)
