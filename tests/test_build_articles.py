import unittest
from pathlib import Path

from scripts.build_articles import (
    ArticleRecord,
    build_payloads,
    build_sitemap_xml,
    derive_subcategory_metadata,
    markdown_to_html,
    propagate_series_cover_images,
    resolve_frontmatter_asset_ref,
    resolve_local_ref,
    validate_filesystem_safe_rel_path,
)


class MarkdownToHtmlBreakTests(unittest.TestCase):
    def test_single_blank_line_keeps_normal_paragraph_break(self) -> None:
        html = markdown_to_html("First paragraph.\n\nSecond paragraph.")

        self.assertEqual(
            html,
            "<p>First paragraph.</p>\n<p>Second paragraph.</p>",
        )

    def test_standalone_backslash_renders_small_break(self) -> None:
        html = markdown_to_html("First paragraph.\n\n\\\n\nSecond paragraph.")

        self.assertIn('article-break article-break--small', html)
        self.assertNotIn("<p>\\</p>", html)
        self.assertEqual(
            html,
            "<p>First paragraph.</p>\n"
            '<div class="article-break article-break--small" aria-hidden="true"></div>\n'
            "<p>Second paragraph.</p>",
        )

    def test_double_blank_lines_render_large_break(self) -> None:
        html = markdown_to_html("First paragraph.\n\n\nSecond paragraph.")

        self.assertIn('article-break article-break--large', html)
        self.assertEqual(
            html,
            "<p>First paragraph.</p>\n"
            '<div class="article-break article-break--large" aria-hidden="true"></div>\n'
            "<p>Second paragraph.</p>",
        )

    def test_mixed_blocks_preserve_break_markers(self) -> None:
        markdown = (
            "# Heading\n"
            "\n"
            "\n"
            "![Alt](./image.png \"Caption\")\n"
            "\n"
            "\\\n"
            "\n"
            "> quoted text\n"
            "\n"
            "- item one\n"
            "- item two\n"
        )

        html = markdown_to_html(markdown)

        self.assertIn("<h1>Heading</h1>", html)
        self.assertIn('article-break article-break--large', html)
        self.assertIn('article-break article-break--small', html)
        self.assertIn('<p class="image-block"><img src="./image.png" alt="Alt" loading="lazy" title="Caption" /></p>', html)
        self.assertIn("<blockquote><p>quoted text</p></blockquote>", html)
        self.assertIn("<ul><li>item one</li><li>item two</li></ul>", html)

    def test_code_blocks_keep_backslashes_literal(self) -> None:
        markdown = (
            "```bash\n"
            "aws ec2 describe-network-interfaces \\\n"
            "  --filters Name=attachment.instance-id,Values=i-123 \\\n"
            "```\n"
            "\n"
            "Next paragraph."
        )

        html = markdown_to_html(markdown)

        self.assertIn("aws ec2 describe-network-interfaces \\\n", html)
        self.assertIn("  --filters Name=attachment.instance-id,Values=i-123 \\", html)
        self.assertNotIn('article-break article-break--small', html)
        self.assertNotIn('article-break article-break--large', html)
        self.assertTrue(html.endswith("<p>Next paragraph.</p>"))

    def test_standalone_embedded_media_line_renders_iframe(self) -> None:
        html = markdown_to_html("[Embedded media](https://www.youtube.com/embed/UY24fK4DJvQ?feature=oembed)")

        self.assertIn('<div class="embedded-media">', html)
        self.assertIn('src="https://www.youtube.com/embed/UY24fK4DJvQ"', html)
        self.assertIn("<iframe", html)
        self.assertNotIn("<a href=", html)

    def test_regular_youtube_link_stays_link(self) -> None:
        html = markdown_to_html(
            "Watch this [video](https://www.youtube.com/watch?v=UY24fK4DJvQ) for reference."
        )

        self.assertIn('<a href="https://www.youtube.com/watch?v=UY24fK4DJvQ"', html)
        self.assertNotIn("<iframe", html)


class LocalAssetResolutionTests(unittest.TestCase):
    def test_invalid_filesystem_chars_are_rejected_for_assets(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            r'filesystem-invalid characters .*reviews/Anime_Manga/Frieren: Beyond Journey\'s End/Shared/image\.png',
        ):
            validate_filesystem_safe_rel_path(
                Path("reviews/Anime_Manga/Frieren: Beyond Journey's End/Shared/image.png")
            )

    def test_parent_shared_asset_path_resolves(self) -> None:
        rewritten = resolve_local_ref(
            Path(
                "reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/English/humanity_part1_philosophy.md"
            ),
            "../Shared/manga_1st_cover.png",
            {},
        )

        self.assertEqual(
            rewritten,
            "assets/articles/reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/Shared/manga_1st_cover.png",
        )

    def test_nested_shared_asset_path_resolves(self) -> None:
        rewritten = resolve_local_ref(
            Path(
                "reviews/Movie/A_Foggy_Tale/English/Part1/en.md"
            ),
            "../../Shared/source_https_www_instagram_com_p_dpsuxclkjzw.png",
            {},
        )

        self.assertEqual(
            rewritten,
            "assets/articles/reviews/Movie/A_Foggy_Tale/Shared/source_https_www_instagram_com_p_dpsuxclkjzw.png",
        )

    def test_filesystem_safe_asset_paths_are_accepted(self) -> None:
        validate_filesystem_safe_rel_path(
            Path("reviews/Anime_Manga/Frieren_Beyond_Journeys_End/Season1_Season2/Shared/image.png")
        )

    def test_frontmatter_cover_path_resolves(self) -> None:
        rewritten = resolve_frontmatter_asset_ref(
            Path(
                "reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/English/humanity_part1_philosophy.md"
            ),
            "../Shared/manga_1st_cover.png",
            "series_cover_image",
        )

        self.assertEqual(
            rewritten,
            "assets/articles/reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/Shared/manga_1st_cover.png",
        )


class ArticleMetadataTests(unittest.TestCase):
    def test_review_subcategory_is_derived_from_folder(self) -> None:
        subcategory_id, subcategory_label = derive_subcategory_metadata(
            ["reviews", "Anime_Manga", "Attack_on_Titan", "English", "part1.md"]
        )

        self.assertEqual(subcategory_id, "Anime_Manga")
        self.assertEqual(subcategory_label, "Anime Manga")

    def test_technical_subcategory_is_derived_from_folder(self) -> None:
        subcategory_id, subcategory_label = derive_subcategory_metadata(
            ["technical", "Operation_Deep_Dive", "Nginx_Load_Balancer_With_Nodejs_Express", "en.md"]
        )

        self.assertEqual(subcategory_id, "Operation_Deep_Dive")
        self.assertEqual(subcategory_label, "Operation Deep Dive")

    def test_other_articles_use_others_subcategory(self) -> None:
        subcategory_id, subcategory_label = derive_subcategory_metadata(
            ["others", "AppWorks_School", "zh.md"]
        )

        self.assertEqual(subcategory_id, "others")
        self.assertEqual(subcategory_label, "Others")


class SearchAndSeriesCoverTests(unittest.TestCase):
    def build_record(
        self,
        *,
        article_id: str,
        lang: str,
        title: str,
        series_id: str,
        series_title: str,
        series_cover_image: str | None,
        body_markdown: str,
        cover_image: str | None = None,
        source_rel: Path | None = None,
    ) -> ArticleRecord:
        resolved_source_rel = source_rel
        if resolved_source_rel is None:
            resolved_source_rel = (
                Path("reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/English/humanity_part1_philosophy.md")
                if lang == "en"
                else Path("reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/Mandarin/humanity_part1_philosophy.md")
            )

        return ArticleRecord(
            meta={
                "id": article_id,
                "lang": lang,
                "title": title,
                "slug": article_id,
                "excerpt": "Excerpt",
                "category": "review",
                "subcategory_id": "Anime_Manga",
                "subcategory_label": "Anime Manga",
                "tags": ["review"],
                "published_at": "2026-01-01",
                "updated_at": None,
                "read_time": 5,
                "external_url": None,
                "cover_image": cover_image,
                "series_cover_image": series_cover_image,
                "draft": False,
                "series_id": series_id,
                "series_title": series_title,
                "series_order": 1,
                "part_number": 1,
            },
            body_markdown=body_markdown,
            body_html=markdown_to_html(body_markdown),
            source_rel=resolved_source_rel,
        )

    def test_series_cover_image_is_propagated_to_other_parts(self) -> None:
        records = [
            self.build_record(
                article_id="series-part-1",
                lang="en",
                title="Part 1",
                series_id="demo-series",
                series_title="Demo Series",
                series_cover_image="assets/articles/reviews/demo/Shared/cover.png",
                body_markdown="Alpha body text.",
            ),
            self.build_record(
                article_id="series-part-2",
                lang="en",
                title="Part 2",
                series_id="demo-series",
                series_title="Demo Series",
                series_cover_image=None,
                body_markdown="Beta body text.",
            ),
        ]

        propagate_series_cover_images(records)

        self.assertEqual(
            records[1].meta["series_cover_image"],
            "assets/articles/reviews/demo/Shared/cover.png",
        )

    def test_conflicting_series_cover_image_values_raise(self) -> None:
        records = [
            self.build_record(
                article_id="series-part-1",
                lang="en",
                title="Part 1",
                series_id="demo-series",
                series_title="Demo Series",
                series_cover_image="assets/articles/reviews/demo/Shared/cover-a.png",
                body_markdown="Alpha body text.",
            ),
            self.build_record(
                article_id="series-part-2",
                lang="zh",
                title="Part 2",
                series_id="demo-series",
                series_title="示範系列",
                series_cover_image="assets/articles/reviews/demo/Shared/cover-b.png",
                body_markdown="Beta body text.",
            ),
        ]

        with self.assertRaisesRegex(ValueError, "Conflicting series_cover_image values"):
            propagate_series_cover_images(records)

    def test_build_payloads_writes_normalized_search_index(self) -> None:
        record = self.build_record(
            article_id="demo-article",
            lang="en",
            title="Cloud Reliability Notes",
            series_id="demo-series",
            series_title="Infra Diaries",
            series_cover_image="assets/articles/reviews/demo/Shared/cover.png",
            body_markdown="# Intro\n\nCache stampede and Kubernetes outages.",
        )

        payloads = build_payloads([record], {"review": {"en": "Review", "zh": "評論"}})
        search_entry = payloads["search"]["articles"]["en"]["demo-article"]

        self.assertEqual(search_entry["title"], "cloud reliability notes")
        self.assertEqual(search_entry["series"], "infra diaries")
        self.assertIn("cache stampede and kubernetes outages.", search_entry["content"])

    def test_build_payloads_infers_preview_images(self) -> None:
        records = [
            self.build_record(
                article_id="demo-article-en",
                lang="en",
                title="Part 1",
                series_id="demo-series",
                series_title="Demo Series",
                series_cover_image=None,
                body_markdown='![Cover](../Shared/manga_1st_cover.png "Cover")\n\nText body.',
            ),
            self.build_record(
                article_id="demo-article-zh",
                lang="zh",
                title="第 1 部",
                series_id="demo-series",
                series_title="示範系列",
                series_cover_image=None,
                body_markdown="只有文字，沒有圖片。",
            ),
        ]

        payloads = build_payloads(records, {"review": {"en": "Review", "zh": "評論"}})
        en_index = next(item for item in payloads["index"]["articles"] if item["lang"] == "en")
        zh_index = next(item for item in payloads["index"]["articles"] if item["lang"] == "zh")

        self.assertEqual(
            en_index["preview_image"],
            "assets/articles/reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/Shared/manga_1st_cover.png",
        )
        self.assertEqual(
            en_index["series_preview_image"],
            "assets/articles/reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/Shared/manga_1st_cover.png",
        )
        self.assertEqual(zh_index["preview_image"], None)
        self.assertEqual(
            zh_index["series_preview_image"],
            "assets/articles/reviews/Anime_Manga/Attack_on_Titan/Humanity_Part1_Philosophy/Shared/manga_1st_cover.png",
        )

    def test_explicit_cover_image_overrides_inferred_preview(self) -> None:
        record = self.build_record(
            article_id="explicit-cover",
            lang="en",
            title="Explicit Cover",
            series_id="explicit-series",
            series_title="Explicit Series",
            series_cover_image=None,
            cover_image="/assets/custom-cover.jpg",
            body_markdown='![Cover](../Shared/manga_1st_cover.png "Cover")\n\nText body.',
        )

        payloads = build_payloads([record], {"review": {"en": "Review", "zh": "評論"}})
        index_item = payloads["index"]["articles"][0]

        self.assertEqual(index_item["preview_image"], "/assets/custom-cover.jpg")
        self.assertEqual(index_item["series_preview_image"], "/assets/custom-cover.jpg")


class SitemapGenerationTests(unittest.TestCase):
    """Cover the build_sitemap_xml helper used to regenerate site/sitemap.xml
    and site-eng/sitemap.xml on every build."""

    SITE_CONFIG = {
        "site_name": "Example",
        "site_url": "https://example.com",
        "author": "Example Author",
    }

    STATIC = (
        ("/", "weekly", "1.0"),
        ("/about.html", "monthly", "0.6"),
    )

    def test_static_entries_are_emitted_with_absolute_urls(self) -> None:
        xml = build_sitemap_xml(self.SITE_CONFIG, self.STATIC, [])

        self.assertIn('<?xml version="1.0" encoding="UTF-8"?>', xml)
        self.assertIn('<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', xml)
        self.assertIn("<loc>https://example.com/</loc>", xml)
        self.assertIn("<loc>https://example.com/about.html</loc>", xml)
        self.assertEqual(xml.count("<url>"), 2)
        self.assertTrue(xml.endswith("</urlset>\n"))

    def test_article_entries_are_appended_after_static_entries(self) -> None:
        article_entries = [
            ("/article.html?id=one&lang=en", "monthly", "0.5"),
            ("/article.html?id=two&lang=zh", "monthly", "0.5"),
        ]

        xml = build_sitemap_xml(self.SITE_CONFIG, self.STATIC, article_entries)

        self.assertEqual(xml.count("<url>"), 4)
        self.assertIn(
            "<loc>https://example.com/article.html?id=one&amp;lang=en</loc>",
            xml,
        )
        self.assertIn(
            "<loc>https://example.com/article.html?id=two&amp;lang=zh</loc>",
            xml,
        )

    def test_article_entries_work_with_engineer_prefix(self) -> None:
        article_entries = [
            ("/engineer/article.html?id=sre&lang=en", "monthly", "0.5"),
        ]
        static = (("/engineer/", "monthly", "0.9"),)

        xml = build_sitemap_xml(self.SITE_CONFIG, static, article_entries)

        self.assertIn(
            "<loc>https://example.com/engineer/article.html?id=sre&amp;lang=en</loc>",
            xml,
        )
        self.assertEqual(xml.count("<url>"), 2)


if __name__ == "__main__":
    unittest.main()
