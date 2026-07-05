import pytest

from publishers.facebook import FacebookPublisher
from shared.models import PostContent


def test_facebook_publish_not_implemented():
    publisher = FacebookPublisher()
    with pytest.raises(NotImplementedError, match="Facebook publisher"):
        publisher.publish(PostContent(text="hello", platform="facebook"))
