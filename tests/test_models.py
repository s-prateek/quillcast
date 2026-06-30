from shared.models import PostRecord, TargetRecord


def test_post_record_round_trip():
    record = PostRecord(
        PostID="post-1",
        CreatedAt="2026-06-29T08:00:00Z",
        UpdatedAt="2026-06-29T08:00:00Z",
        Topic="AI agents in enterprise",
        SourceURL="https://example.com/article",
        SourceType="rss",
        OverallStatus="PENDING",
        ContentVariants={"linkedin": "Draft text"},
        Targets={"linkedin": TargetRecord()},
    )

    restored = PostRecord.from_item(record.to_item())

    assert restored.PostID == record.PostID
    assert restored.ContentVariants == record.ContentVariants
    assert restored.Targets["linkedin"].Status == "DRAFT"
