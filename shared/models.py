from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PostContent:
    text: str
    platform: str
    media_urls: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    success: bool
    platform_post_id: str | None = None
    error: str | None = None


@dataclass
class TopicCandidate:
    id: str
    title: str
    hook: str
    source_url: str
    source_type: str  # rss | evergreen


@dataclass
class TargetRecord:
    Status: str = "DRAFT"
    EditedContent: str | None = None
    PlatformPostID: str | None = None
    PublishedAt: str | None = None
    ErrorLog: str | None = None
    RetryCount: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "Status": self.Status,
            "EditedContent": self.EditedContent,
            "PlatformPostID": self.PlatformPostID,
            "PublishedAt": self.PublishedAt,
            "ErrorLog": self.ErrorLog,
            "RetryCount": self.RetryCount,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TargetRecord:
        return cls(
            Status=data.get("Status", "DRAFT"),
            EditedContent=data.get("EditedContent"),
            PlatformPostID=data.get("PlatformPostID"),
            PublishedAt=data.get("PublishedAt"),
            ErrorLog=data.get("ErrorLog"),
            RetryCount=int(data.get("RetryCount", 0)),
        )


@dataclass
class PostRecord:
    PostID: str
    CreatedAt: str
    UpdatedAt: str
    Topic: str
    SourceURL: str
    SourceType: str
    OverallStatus: str
    ContentVariants: dict[str, Any]
    Targets: dict[str, TargetRecord]

    def to_item(self) -> dict[str, Any]:
        return {
            "PostID": self.PostID,
            "CreatedAt": self.CreatedAt,
            "UpdatedAt": self.UpdatedAt,
            "Topic": self.Topic,
            "SourceURL": self.SourceURL,
            "SourceType": self.SourceType,
            "OverallStatus": self.OverallStatus,
            "ContentVariants": self.ContentVariants,
            "Targets": {platform: target.to_dict() for platform, target in self.Targets.items()},
        }

    @classmethod
    def from_item(cls, item: dict[str, Any]) -> PostRecord:
        return cls(
            PostID=item["PostID"],
            CreatedAt=item["CreatedAt"],
            UpdatedAt=item["UpdatedAt"],
            Topic=item["Topic"],
            SourceURL=item["SourceURL"],
            SourceType=item["SourceType"],
            OverallStatus=item["OverallStatus"],
            ContentVariants=item["ContentVariants"],
            Targets={
                platform: TargetRecord.from_dict(target)
                for platform, target in item["Targets"].items()
            },
        )
