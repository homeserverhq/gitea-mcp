# Gitea MCP Multitenant Proxy Server

This repository contains a Model Context Protocol (MCP) server that acts as a
secure, multi-tenant proxy between an AI assistant and the Gitea API.

It exposes **257 text-only MCP tools** covering repositories, issues, pull
requests, releases, branches, tags, repository contents, commits, wiki, topics,
organizations, teams, users, notifications, packages, and server health.

## Features

- **Identity passthrough** — forwards the incoming `Authorization: Bearer <token>`
  header to Gitea. No server-side credential store.
- **Multi-tenancy** — uses Python `contextvars` so concurrent users remain isolated.
- **Text-only** — no binary or multipart endpoints. File and wiki content is
  exchanged as base64 strings inside JSON.
- **TOON compression** — bulk list responses are compressed with TOON.
- **Efficient gets** — GET responses return common fields by default; pass
  `include_all_fields=true` for the full object.
- **Package helper** — `upload_generic_package` uploads a text file as a Gitea
  generic package so package linking/unlinking can be exercised end to end.
- **Admin sudo** — every tool accepts an optional `sudo` username, forwarded as
  Gitea's documented `Sudo` header (admin only).
- **Datetime compatibility** — tool-facing datetimes use the standard ISO 8601
  format with explicit offset; the client converts them to the RFC3339 form
  Gitea requires internally.

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GITEA_BASE_URL` | Yes | Docker-internal Gitea API URL, including `/api/v1` |
| `MCP_SERVER_PORT` | Yes | Port the MCP server listens on |
| `API_KEY` | No | Used by the test runner / clients that do not pass a Bearer token |
| `ALLOW_ALL_AGGREGATE` | No | When `true`, aggregate list tools honor `include_all_fields` |
| `IS_STATEFUL` | No | When `true`, use stateful Streamable HTTP sessions |

## Installation and Local Development

```bash
pip install fastmcp httpx pydantic uvicorn toon-mcp-server
export GITEA_BASE_URL="http://gitea-app:3000/api/v1"
export MCP_SERVER_PORT=6880
python -m src.main
```

The MCP endpoint is `http://<host>:<port>/mcp` (Streamable HTTP).

## Docker

```bash
docker build -t gitea-mcp:latest .
docker run -d --name gitea-mcp --network dock-ext \
  -p 6880:6880 \
  -e GITEA_BASE_URL="http://gitea-app:3000/api/v1" \
  -e MCP_SERVER_PORT=6880 \
  -e API_KEY="<gitea-api-key>" \
  -e ALLOW_ALL_AGGREGATE=true \
  -e IS_STATEFUL=false \
  gitea-mcp:latest
```

## Tool Behavior

- **List/search tools** return a domain key whose value is TOON, for example
  `{"issues": "[...TOON...]"}`
- **Single GET tools** return a JSON object filtered to common fields unless
  `include_all_fields=true`.
- **Create/update tools** honor `ALLOW_ALL_AGGREGATE` for field filtering.
- **Delete tools** return `{"status":"ok"}` for empty responses.
- **Path identifiers** are passed as explicit path parameters (`owner`, `repo`,
  `index`, `id`, `branch`, `tag`, `sha`, `pageName`, etc.).
- **`sudo`** is available on every tool and is only usable by Gitea admins.

## Testing

The test harness uses only MCP calls — it never calls the Gitea API directly.
It provisions a temporary repository, exercises every tool, verifies cleanup,
and fails if any discovered tool was not invoked.

```bash
MCP_SERVER_PORT=6880 API_KEY="<gitea-api-key>" python -m src.test_runner
```

Latest result: **299 assertions passed, 0 failed**, with full tool coverage and
leak detection.

### Test residue cleanup

Gitea retains `action` rows when a repository is deleted. If a deleted test repo
is referenced by a feed action, the user activity feed can render
`(non-existing-repo)/(non-existing-repo)` or return HTTP 500.

The test harness now deletes organization repositories individually so Gitea
cascades their actions. As a safety check, run:

```bash
docker exec -e PGPASSWORD="$GITEA_DB_PASSWORD" \
  -e PGUSER="$GITEA_DB_USER" -e PGDATABASE="$GITEA_DB_NAME" \
  -i gitea-db sh -s -- --check < scripts/cleanup_orphaned_actions.sh
```

Exit code `0` means no orphaned actions. To remove any that exist:

```bash
docker exec -e PGPASSWORD="$GITEA_DB_PASSWORD" \
  -e PGUSER="$GITEA_DB_USER" -e PGDATABASE="$GITEA_DB_NAME" \
  -i gitea-db sh -s < scripts/cleanup_orphaned_actions.sh
```

The script uses the standard `PGHOST`, `PGPORT`, `PGUSER`, `PGDATABASE`, and
`PGPASSWORD` variables. `PGHOST` and `PGPORT` default to `localhost:5432` for
running inside the database container.

## Gitea Version Note

The running Gitea instance is **1.25.2** and exposes 467 v1 operations. The
checkout in `/repos/gitea` contains a newer route set than the running binary.
This server is generated against the **running instance's** swagger so that every
implemented endpoint can be tested against the live backend. Source-only routes
(such as some project and newer review endpoints) are intentionally omitted.

## Tool Inventory

- `notify_get_list` — List users's notification threads
- `notify_read_list` — Mark notification threads as read, pinned or unread
- `notify_new_available` — Check if unread notifications exist
- `notify_get_thread` — Get notification thread by ID
- `notify_read_thread` — Mark notification thread as read by ID
- `create_org_repo_deprecated` — Create a repository in an organization
- `org_get_all` — Get list of organizations
- `org_create` — Create an organization
- `org_delete` — Delete an organization
- `org_get` — Get an organization
- `org_edit` — Edit an organization
- `org_list_activity_feeds` — List an organization's activity feeds
- `org_list_labels` — List an organization's labels
- `org_create_label` — Create a label for an organization
- `org_delete_label` — Delete a label
- `org_get_label` — Get a single label
- `org_edit_label` — Update a label
- `org_list_members` — List an organization's members
- `org_delete_member` — Remove a member from an organization
- `org_is_member` — Check if a user is a member of an organization
- `org_list_public_members` — List an organization's public members
- `org_conceal_member` — Conceal a user's membership
- `org_is_public_member` — Check if a user is a public member of an organization
- `org_publicize_member` — Publicize a user's membership
- `rename_org` — Rename an organization
- `org_list_repos` — List an organization's repos
- `create_org_repo` — Create a repository in an organization
- `org_list_teams` — List an organization's teams
- `org_create_team` — Create a team
- `team_search` — Search for teams within an organization
- `list_packages` — Gets all packages of an owner
- `list_package_versions` — Gets all versions of a package
- `get_latest_package_version` — Gets the latest version of a package
- `link_package` — Link a package to a repository
- `unlink_package` — Unlink a package from a repository
- `delete_package` — Delete a package
- `get_package` — Gets a package
- `list_package_files` — Gets all files of a package
- `issue_search_issues` — Search for issues across the repositories that the user has access to
- `repo_migrate` — Migrate a remote git repository
- `repo_search` — Search for repositories
- `repo_delete` — Delete a repository
- `repo_get` — Get a repository
- `repo_edit` — Edit a repository's properties. Only fields that are set will be changed.
- `repo_list_activity_feeds` — List a repository's activity feeds
- `repo_get_assignees` — Return all users that have write access and can be assigned to issues
- `repo_list_branch_protection` — List branch protections for a repository
- `repo_create_branch_protection` — Create a branch protections for a repository
- `repo_update_branch_protection_priories` — Update the priorities of branch protections for a repository.
- `repo_delete_branch_protection` — Delete a specific branch protection for the repository
- `repo_get_branch_protection` — Get a specific branch protection for the repository
- `repo_edit_branch_protection` — Edit a branch protections for a repository. Only fields that are set will be changed
- `repo_list_branches` — List a repository's branches
- `repo_create_branch` — Create a branch
- `repo_delete_branch` — Delete a specific branch from a repository
- `repo_get_branch` — Retrieve a specific branch from a repository, including its effective branch protection
- `repo_rename_branch` — Rename a branch
- `repo_list_collaborators` — List a repository's collaborators
- `repo_delete_collaborator` — Delete a collaborator from a repository
- `repo_check_collaborator` — Check if a user is a collaborator of a repository
- `repo_add_collaborator` — Add or Update a collaborator to a repository
- `repo_get_repo_permissions` — Get repository permissions for a user
- `repo_get_all_commits` — Get a list of all commits from a repository
- `repo_get_combined_status_by_ref` — Get a commit's combined status, by branch/tag/commit reference
- `repo_list_statuses_by_ref` — Get a commit's statuses, by branch/tag/commit reference
- `repo_get_commit_pull_request` — Get the merged pull request of the commit
- `repo_compare_diff` — Get commit comparison information
- `repo_get_contents_list` — Gets the metadata of all the entries of the root dir.
- `repo_change_files` — Modify multiple files in a repository
- `repo_delete_file` — Delete a file in a repository
- `repo_get_contents` — Gets the metadata and contents (if a file) of an entry in a repository, or a list of entries if a dir.
- `repo_create_file` — Create a file in a repository
- `repo_update_file` — Update a file in a repository
- `repo_apply_diff_patch` — Apply diff patch to repository
- `list_forks` — List a repository's forks
- `create_fork` — Fork a repository
- `get_blob` — Gets the blob of a repository.
- `repo_get_single_commit` — Get a single commit from a repository
- `repo_list_all_git_refs` — Get specified ref or filtered repository's refs
- `repo_list_git_refs` — Get specified ref or filtered repository's refs
- `get_annotated_tag` — Gets the tag object of an annotated tag (not lightweight tags)
- `get_tree` — Gets the tree of a repository.
- `repo_get_issue_templates` — Get available issue templates for a repository
- `issue_list_issues` — List a repository's issues
- `issue_create_issue` — Create an issue. If using deadline only the date will be taken into account, and time of day ignored.
- `issue_get_repo_comments` — List all comments in a repository
- `issue_delete_comment` — Delete a comment
- `issue_get_comment` — Get a comment
- `issue_edit_comment` — Edit a comment
- `issue_delete_comment_reaction` — Remove a reaction from a comment of an issue
- `issue_get_comment_reactions` — Get a list of reactions from a comment of an issue
- `issue_post_comment_reaction` — Add a reaction to a comment of an issue
- `repo_list_pinned_issues` — List a repo's pinned issues
- `issue_delete` — Delete an issue
- `issue_get_issue` — Get an issue
- `issue_edit_issue` — Edit an issue. If using deadline only the date will be taken into account, and time of day ignored.
- `issue_remove_issue_blocking` — Unblock the issue given in the body by the issue in path
- `issue_list_blocks` — List issues that are blocked by this issue
- `issue_create_issue_blocking` — Block the issue given in the body by the issue in path
- `issue_get_comments` — List all comments on an issue
- `issue_create_comment` — Add a comment to an issue
- `issue_delete_comment_deprecated` — Delete a comment
- `issue_edit_comment_deprecated` — Edit a comment
- `issue_edit_issue_deadline` — Set an issue deadline. If set to null, the deadline is deleted. If using deadline only the date will be taken into account, and time of day ignored.
- `issue_remove_issue_dependencies` — Remove an issue dependency
- `issue_list_issue_dependencies` — List an issue's dependencies, i.e all issues that block this issue.
- `issue_create_issue_dependencies` — Make the issue in the url depend on the issue in the form.
- `issue_clear_labels` — Remove all labels from an issue
- `issue_get_labels` — Get an issue's labels
- `issue_add_label` — Add a label to an issue
- `issue_replace_labels` — Replace an issue's labels
- `issue_remove_label` — Remove a label from an issue
- `issue_unlock_issue` — Unlock an issue
- `issue_lock_issue` — Lock an issue
- `unpin_issue` — Unpin an Issue
- `pin_issue` — Pin an Issue
- `move_issue_pin` — Moves the Pin to the given Position
- `issue_delete_issue_reaction` — Remove a reaction from an issue
- `issue_get_issue_reactions` — Get a list reactions of an issue
- `issue_post_issue_reaction` — Add a reaction to an issue
- `issue_delete_stop_watch` — Delete an issue's existing stopwatch.
- `issue_start_stop_watch` — Start stopwatch on an issue.
- `issue_stop_stop_watch` — Stop an issue's existing stopwatch.
- `issue_subscriptions` — Get users who subscribed on an issue.
- `issue_check_subscription` — Check if user is subscribed to an issue
- `issue_delete_subscription` — Unsubscribe user from issue
- `issue_add_subscription` — Subscribe user to issue
- `issue_get_comments_and_timeline` — List all comments and events on an issue
- `issue_reset_time` — Reset a tracked time of an issue
- `issue_tracked_times` — List an issue's tracked times
- `issue_add_time` — Add tracked time to a issue
- `issue_delete_time` — Delete specific tracked time
- `repo_list_keys` — List a repository's keys
- `repo_create_key` — Add a key to a repository
- `repo_delete_key` — Delete a key from a repository
- `repo_get_key` — Get a repository's key by id
- `issue_list_labels` — Get all of a repository's labels
- `issue_create_label` — Create a label
- `issue_delete_label` — Delete a label
- `issue_get_label` — Get a single label
- `issue_edit_label` — Update a label
- `repo_get_languages` — Get languages and number of bytes of code written
- `repo_get_licenses` — Get repo licenses
- `repo_merge_upstream` — Merge a branch from upstream
- `issue_get_milestones_list` — Get all of a repository's opened milestones
- `issue_create_milestone` — Create a milestone
- `issue_delete_milestone` — Delete a milestone
- `issue_get_milestone` — Get a milestone
- `issue_edit_milestone` — Update a milestone
- `notify_get_repo_list` — List users's notification threads on a specific repo
- `notify_read_repo_list` — Mark notification threads as read, pinned or unread on a specific repo
- `repo_list_pull_requests` — List a repo's pull requests
- `repo_create_pull_request` — Create a pull request
- `repo_list_pinned_pull_requests` — List a repo's pinned pull requests
- `repo_get_pull_request_by_base_head` — Get a pull request by base and head
- `repo_get_pull_request` — Get a pull request
- `repo_edit_pull_request` — Update a pull request. If using deadline only the date will be taken into account, and time of day ignored.
- `repo_get_pull_request_commits` — Get commits for a pull request
- `repo_get_pull_request_files` — Get changed files for a pull request
- `repo_cancel_scheduled_auto_merge` — Cancel the scheduled auto merge for the given pull request
- `repo_pull_request_is_merged` — Check if a pull request has been merged
- `repo_merge_pull_request` — Merge a pull request
- `repo_delete_pull_review_requests` — cancel review requests for a pull request
- `repo_create_pull_review_requests` — create review requests for a pull request
- `repo_list_pull_reviews` — List all reviews for a pull request
- `repo_create_pull_review` — Create a review to an pull request
- `repo_delete_pull_review` — Delete a specific review from a pull request
- `repo_get_pull_review` — Get a specific review for a pull request
- `repo_submit_pull_review` — Submit a pending review to an pull request
- `repo_get_pull_review_comments` — Get a specific review for a pull request
- `repo_dismiss_pull_review` — Dismiss a review for a pull request
- `repo_un_dismiss_pull_review` — Cancel to dismiss a review for a pull request
- `repo_update_pull_request` — Merge PR's baseBranch into headBranch
- `repo_list_releases` — List a repo's releases
- `repo_create_release` — Create a release
- `repo_get_latest_release` — Gets the most recent non-prerelease, non-draft release of a repository, sorted by created_at
- `repo_delete_release_by_tag` — Delete a release by tag name
- `repo_get_release_by_tag` — Get a release by tag name
- `repo_delete_release` — Delete a release
- `repo_get_release` — Get a release
- `repo_edit_release` — Update a release
- `repo_get_reviewers` — Return all users that can be requested to review in this repo
- `repo_list_statuses` — Get a commit's statuses
- `repo_create_status` — Create a commit status
- `user_current_delete_subscription` — Unwatch a repo
- `user_current_check_subscription` — Check if the current user is watching a repo
- `user_current_put_subscription` — Watch a repo
- `repo_list_tag_protection` — List tag protections for a repository
- `repo_create_tag_protection` — Create a tag protections for a repository
- `repo_delete_tag_protection` — Delete a specific tag protection for the repository
- `repo_get_tag_protection` — Get a specific tag protection for the repository
- `repo_edit_tag_protection` — Edit a tag protections for a repository. Only fields that are set will be changed
- `repo_list_tags` — List a repository's tags
- `repo_create_tag` — Create a new git tag in a repository
- `repo_delete_tag` — Delete a repository's tag by name
- `repo_get_tag` — Get the tag of a repository by tag name
- `repo_list_teams` — List a repository's teams
- `repo_delete_team` — Delete a team from a repository
- `repo_check_team` — Check if a team is assigned to a repository
- `repo_add_team` — Add a team to a repository
- `repo_tracked_times` — List a repo's tracked times
- `user_tracked_times` — List a user's tracked times in a repo
- `repo_list_topics` — Get list of topics that a repository has
- `repo_update_topics` — Replace list of topics for a repository
- `repo_delete_topic` — Delete a topic from a repository
- `repo_add_topic` — Add a topic to a repository
- `repo_create_wiki_page` — Create a wiki page
- `repo_delete_wiki_page` — Delete a wiki page
- `repo_get_wiki_page` — Get a wiki page
- `repo_edit_wiki_page` — Edit a wiki page
- `repo_get_wiki_pages` — Get all wiki pages
- `repo_get_wiki_page_revisions` — Get revisions of a wiki page
- `generate_repo` — Create a repository using a template
- `repo_get_by_id` — Get a repository by id
- `org_delete_team` — Delete a team
- `org_get_team` — Get a team
- `org_edit_team` — Edit a team
- `org_list_team_activity_feeds` — List a team's activity feeds
- `org_list_team_members` — List a team's members
- `org_remove_team_member` — Remove a team member
- `org_list_team_member` — List a particular member of team
- `org_add_team_member` — Add a team member
- `org_list_team_repos` — List a team's repos
- `org_remove_team_repository` — Remove a repository from a team
- `org_list_team_repo` — List a particular repo of team
- `org_add_team_repository` — Add a repository to a team
- `topic_search` — search topics via keyword
- `user_get_current` — Get the authenticated user
- `user_current_list_followers` — List the authenticated user's followers
- `user_current_list_following` — List the users that the authenticated user is following
- `user_current_delete_follow` — Unfollow a user
- `user_current_check_following` — Check whether a user is followed by the authenticated user
- `user_current_put_follow` — Follow a user
- `org_list_current_user_orgs` — List the current user's organizations
- `user_current_list_repos` — List the repos that the authenticated user owns
- `create_current_user_repo` — Create a repository
- `user_current_list_starred` — The repos that the authenticated user has starred
- `user_get_stop_watches` — Get list of all existing stopwatches
- `user_current_list_subscriptions` — List repositories watched by the authenticated user
- `user_list_teams` — List all the teams a user belongs to
- `user_current_tracked_times` — List the current user's tracked times
- `user_search` — Search for users
- `user_get` — Get a user
- `user_list_activity_feeds` — List a user's activity feeds
- `user_list_followers` — List the given user's followers
- `user_list_following` — List the users that the given user is following
- `user_check_following` — Check if one user is following another user
- `user_list_gpg_keys` — List the given user's GPG keys
- `user_get_heatmap_data` — Get a user's heatmap
- `user_list_keys` — List the given user's public keys
- `org_list_user_orgs` — List a user's organizations
- `org_get_user_permissions` — Get user permissions in organization
- `user_list_repos` — List the repos owned by the given user
- `user_list_starred` — The repos that the given user has starred
- `user_list_subscriptions` — List the repositories watched by a user
- `get_version` — Returns the version of the Gitea application
- `upload_generic_package` — Upload a text file as a Gitea generic package (text-only helper).
