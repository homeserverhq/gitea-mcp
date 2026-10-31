# Gitea MCP Quick Reference

All tools accept `include_all_fields` where applicable, and an optional admin-only
`sudo` username. Datetimes use ISO 8601 with an explicit offset, for example
`2026-06-22T15:00:00-04:00`.

## Health and discovery

```json
{"tool": "get_version", "arguments": {}}
```

List tools through MCP `tools/list`.

## Repositories

```json
{"tool": "repo_search", "arguments": {"q": "my-repo", "limit": 20}}
{"tool": "repo_get", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "create_current_user_repo", "arguments": {"name": "demo", "description": "Demo repo", "auto_init": true, "private": false}}
{"tool": "repo_edit", "arguments": {"owner": "solo", "repo": "demo", "description": "Updated description"}}
{"tool": "repo_delete", "arguments": {"owner": "solo", "repo": "demo"}}
```

Common reads:

```json
{"tool": "repo_list_branches", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_list_tags", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_list_releases", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_get_contents_list", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_get_contents", "arguments": {"owner": "solo", "repo": "demo", "filepath": "README.md"}}
{"tool": "repo_get_all_commits", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_get_wiki_pages", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_list_topics", "arguments": {"owner": "solo", "repo": "demo"}}
```

## Branches, tags, files

```json
{"tool": "repo_create_branch", "arguments": {"owner": "solo", "repo": "demo", "new_branch_name": "feature", "old_branch_name": "main"}}
{"tool": "repo_create_tag", "arguments": {"owner": "solo", "repo": "demo", "tag_name": "v1.0.0", "message": "Release 1.0.0"}}
{"tool": "repo_create_file", "arguments": {"owner": "solo", "repo": "demo", "filepath": "docs/readme.txt", "content": "<base64>", "message": "Add readme", "branch": "feature"}}
{"tool": "repo_update_file", "arguments": {"owner": "solo", "repo": "demo", "filepath": "docs/readme.txt", "content": "<base64>", "sha": "<blob-sha>", "message": "Update readme", "branch": "feature"}}
{"tool": "repo_delete_file", "arguments": {"owner": "solo", "repo": "demo", "filepath": "docs/readme.txt", "sha": "<blob-sha>", "message": "Remove readme", "branch": "feature"}}
```

File and wiki `content` values are base64 strings.

## Issues

```json
{"tool": "issue_list_issues", "arguments": {"owner": "solo", "repo": "demo", "state": "open"}}
{"tool": "issue_create_issue", "arguments": {"owner": "solo", "repo": "demo", "title": "Bug report", "body": "Steps to reproduce..."}}
{"tool": "issue_get_issue", "arguments": {"owner": "solo", "repo": "demo", "index": 1}}
{"tool": "issue_edit_issue", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "title": "Updated title", "assignees": ["amanda"]}}
{"tool": "issue_create_comment", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "body": "Confirmed."}}
{"tool": "issue_add_label", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "labels": [2]}}
{"tool": "issue_add_time", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "time": 3600}}
{"tool": "issue_create_issue_dependencies", "arguments": {"owner": "solo", "repo": "demo", "index": "1", "body_index": 2, "body_owner": "solo", "body_repo": "demo"}}
```

## Labels and milestones

```json
{"tool": "issue_list_labels", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "issue_create_label", "arguments": {"owner": "solo", "repo": "demo", "name": "bug", "color": "#d73a4a", "description": "Something is broken"}}
{"tool": "issue_create_milestone", "arguments": {"owner": "solo", "repo": "demo", "title": "v1.0", "description": "First release", "due_on": "2026-12-31T00:00:00+00:00"}}
```

## Pull requests

```json
{"tool": "repo_create_pull_request", "arguments": {"owner": "solo", "repo": "demo", "head": "feature", "base": "main", "title": "Add feature", "body": "Implements..."}}
{"tool": "repo_list_pull_requests", "arguments": {"owner": "solo", "repo": "demo", "state": "open"}}
{"tool": "repo_get_pull_request", "arguments": {"owner": "solo", "repo": "demo", "index": 1}}
{"tool": "repo_create_pull_review", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "event": "COMMENT", "body": "Looks good"}}
{"tool": "repo_create_pull_review_requests", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "reviewers": ["amanda"]}}
{"tool": "repo_merge_pull_request", "arguments": {"owner": "solo", "repo": "demo", "index": 1, "Do": "merge"}}
{"tool": "repo_pull_request_is_merged", "arguments": {"owner": "solo", "repo": "demo", "index": 1}}
```

## Releases and wiki

```json
{"tool": "repo_create_release", "arguments": {"owner": "solo", "repo": "demo", "tag_name": "v1.0.0", "name": "v1.0.0", "body": "Release notes"}}
{"tool": "repo_get_latest_release", "arguments": {"owner": "solo", "repo": "demo"}}
{"tool": "repo_create_wiki_page", "arguments": {"owner": "solo", "repo": "demo", "title": "Home", "content_base64": "<base64>", "message": "Create home"}}
{"tool": "repo_get_wiki_page", "arguments": {"owner": "solo", "repo": "demo", "pageName": "Home"}}
```

## Organizations and teams

```json
{"tool": "org_create", "arguments": {"username": "acme", "description": "Acme org", "visibility": "public"}}
{"tool": "org_create_team", "arguments": {"org": "acme", "name": "developers", "permission": "write", "description": "Developers", "units": ["repo.code", "repo.issues", "repo.pulls", "repo.releases", "repo.wiki", "repo.projects", "repo.packages", "repo.actions"]}}
{"tool": "org_add_team_member", "arguments": {"id": 1, "username": "amanda"}}
{"tool": "org_add_team_repository", "arguments": {"id": 1, "org": "acme", "repo": "demo"}}
```

## Users

```json
{"tool": "user_get_current", "arguments": {}}
{"tool": "user_search", "arguments": {"q": "amanda"}}
{"tool": "user_get", "arguments": {"username": "amanda"}}
{"tool": "user_list_repos", "arguments": {"username": "amanda"}}
{"tool": "user_current_list_followers", "arguments": {}}
{"tool": "user_current_put_follow", "arguments": {"username": "amanda"}}
{"tool": "user_check_following", "arguments": {"username": "<current-user>", "target": "amanda"}}
```

## Notifications

```json
{"tool": "notify_get_list", "arguments": {"all": true}}
{"tool": "notify_new_available", "arguments": {}}
{"tool": "notify_get_thread", "arguments": {"id": "7"}}
{"tool": "notify_read_thread", "arguments": {"id": "7", "to_status": "read"}}
{"tool": "notify_read_list", "arguments": {"all": "true", "to_status": "read"}}
```

## Packages

```json
{"tool": "upload_generic_package", "arguments": {"owner": "solo", "package_name": "demo-package", "version": "1.0.0", "filename": "readme.txt", "content": "hello"}}
{"tool": "list_packages", "arguments": {"owner": "solo"}}
{"tool": "get_package", "arguments": {"owner": "solo", "type": "generic", "name": "demo-package", "version": "1.0.0"}}
{"tool": "link_package", "arguments": {"owner": "solo", "type": "generic", "name": "demo-package", "repo_name": "demo"}}
{"tool": "unlink_package", "arguments": {"owner": "solo", "type": "generic", "name": "demo-package"}}
{"tool": "delete_package", "arguments": {"owner": "solo", "type": "generic", "name": "demo-package"}}
```

## Pagination and TOON

- List tools accept `page` (default `1`) and `limit` (default `50`).
- Bulk list responses are returned as TOON strings under a domain key.
- Set `include_all_fields=true` to return full objects instead of common fields.
