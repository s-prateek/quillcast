import pytest

from publishers.blog.ghost import GhostPublisher
from publishers.facebook import FacebookPublisher
from shared.models import PostContent


def test_facebook_publish_not_implemented():
    publisher = FacebookPublisher()
    with pytest.raises(NotImplementedError, match="Facebook publisher"):
        publisher.publish(PostContent(text="hello", platform="facebook"))


def test_ghost_publish_not_implemented():
    publisher = GhostPublisher()
    with pytest.raises(NotImplementedError, match="Ghost blog publisher"):
        publisher.publish(PostContent(text="hello", platform="blog"))
