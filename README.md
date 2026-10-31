# Gitea MCP Multitenant Proxy Server

This repository contains a Model Context Protocol (MCP) server that acts
as a secure, multi-tenant proxy between an AI Assistant and the Gitea
backend API. It exposes **317 MCP tools** covering **23 resource domains**
with full CRUD, search, and repository management.

## ✨ Features

- **🔑 Identity Passthrough** — Extracts the `Authorization: Bearer <token>`
  header from incoming HTTP requests and forwards it to the Gitea API
  without server-side authentication.
- **👥 Multi-Tenancy** — Uses Python `contextvars` to maintain thread-safe
  user identity isolation, ensuring all AI-driven actions are scoped to
  the authenticated user's permissions.
- **📊 Full Gitea Coverage** — 317 text-only tools mapped to Gitea API
  endpoints across 23 resource domains.
- **⚡ TOON Optimization** — Bulk list responses are automatically compressed
  using TOON (Token-Optimized Object Notation) to reduce token consumption
  and maximize context window efficiency.
- **🚀 Efficient Gets** — GET responses return only commonly used fields by
  default. Full objects are available via an `include_all_fields` flag.
- **🧪 Comprehensive Testing** — 364 automated tests covering all tool
  domains, run via the test runner pipeline.
- **🏷️ Tool Annotations** — All tools expose standard MCP ToolAnnotations hints (readOnlyHint, destructiveHint, idempotentHint, openWorldHint). The tags field carries grouping metadata (basic/primary/advanced + gitea).

## 🔧 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GITEA_BASE_URL` | Yes | Docker-internal URL of the Gitea API (e.g. `http://gitea-app:3000/api/v1`) |
| `MCP_SERVER_PORT` | Yes | Port number the MCP server listens on |
| `ALLOW_ALL_AGGREGATE` | No | When `true`, aggregate listing tools honor the `include_all_fields` parameter. When `false` (default), the parameter is silently forced to `False` for aggregate list operations. |
| `IS_STATEFUL` | No | When `true`, uses stateful Streamable HTTP with session tracking. When `false` (default), uses stateless mode. |

## 📦 Installation & Local Development

1. Ensure you have Python 3.12+ installed.
2. Install dependencies:
    ```bash
    pip install fastmcp httpx pydantic uvicorn toon-mcp-server
    ```
3. Run the server:
    ```bash
    export GITEA_BASE_URL=http://gitea-app:3000/api/v1
    export MCP_SERVER_PORT=80
    python -m src.main
    ```

## 🐳 Docker Deployment

Build and run the server using Docker:

```bash
docker build -t gitea-mcp:latest .
docker run -d --name gitea-mcp \
    -e GITEA_BASE_URL="http://gitea-app:3000/api/v1" \
    -e MCP_SERVER_PORT=80 \
    gitea-mcp:latest
```

The MCP server serves at `http://gitea-mcp:80/mcp` (Streamable HTTP).

## ⚠️ Important Notes

- **📋 `include_all_fields`** — The `include_all_fields` parameter (available
  on all `get_*` and `list_*` tools) controls whether all available fields
  are included in responses. Defaults to `False` for performance; set to
  `True` only when additional fields are needed.
- **🔒 `ALLOW_ALL_AGGREGATE`** — Controls whether aggregate listing tools respect the `include_all_fields` parameter. When set to `false` (default), all aggregate list operations silently return only default fields regardless of the caller's request.
- **⚡ TOON Compression** — All bulk list responses are automatically
  compressed using TOON to reduce token consumption by 30–60%.
- **📝 Required Fields & Defaults** — Each `create_*` tool requires specific
  key fields. `description` is mandatory on create tools that expose it, and
  `body` is mandatory for issue, pull request, release, and comment creation.
  All other fields default to empty strings or reasonable values. Datetime
  values use ISO 8601 with an explicit offset.

## 🛠️ API Tool Mapping

The server implements 257 MCP tools organized into the following categories:

### 🏗️ Repositories (23 tools)

- `get_version` — Get the Gitea server version
- `create_current_user_repo` — Create a repository for the authenticated user
- `create_org_repo` — Create a repository in an organization
- `create_org_repo_deprecated` — Create a repository in an organization using the deprecated /org route
- `repo_get` — Get a repository
- `repo_get_by_id` — Get a repository by ID
- `repo_search` — Search for repositories
- `repo_edit` — Edit a repository's properties
- `repo_delete` — Delete a repository
- `repo_migrate` — Migrate a remote git repository
- `generate_repo` — Create a repository using a template
- `create_fork` — Fork a repository
- `list_forks` — List a repository's forks
- `repo_merge_upstream` — Merge a branch from upstream
- `repo_get_assignees` — List users who can be assigned to issues in a repository
- `repo_get_reviewers` — List users who can be requested as reviewers
- `repo_get_languages` — Get repository language statistics
- `repo_get_licenses` — Get repository licenses
- `repo_list_activity_feeds` — List a repository's activity feeds
- `repo_get_issue_templates` — Get available issue templates for a repository
- `repo_list_pinned_issues` — List pinned issues
- `repo_list_pinned_pull_requests` — List pinned pull requests
- `repo_check_assignee` — Check whether a user can be assigned to issues in a repository

### 🌿 Branches & Tags (10 tools)

- `repo_list_branches` — List repository branches
- `repo_create_branch` — Create a branch
- `repo_delete_branch` — Delete a branch
- `repo_get_branch` — Get a repository branch, including effective branch protection
- `repo_rename_branch` — Rename a branch
- `repo_list_tags` — List repository tags
- `repo_create_tag` — Create a git tag
- `repo_delete_tag` — Delete a tag by name
- `repo_get_tag` — Get a repository tag by name
- `repo_update_branch` — Update a branch reference to a new commit

### 📄 Contents, Commits & Git (19 tools)

- `repo_get_contents_list` — Get metadata for all entries in the repository root
- `repo_get_contents` — Get repository file or directory contents
- `repo_create_file` — Create a file in a repository
- `repo_update_file` — Update a file in a repository if SHA is set, or create the file if SHA is not set
- `repo_delete_file` — Delete a file in a repository
- `repo_change_files` — Modify multiple files in a repository
- `repo_apply_diff_patch` — Apply diff patch to repository
- `repo_get_all_commits` — Get a list of all commits from a repository
- `repo_get_single_commit` — Get a single commit from a repository, it has a GitHub-compatible alias "/repos/{owner}/{repo}/commits/{ref}"
- `repo_compare_diff` — Get commit comparison information
- `repo_get_combined_status_by_ref` — Get a commit's combined status, by branch/tag/commit reference
- `repo_list_statuses_by_ref` — Get a commit's statuses, by branch/tag/commit reference
- `repo_list_statuses` — Get a commit's statuses
- `repo_create_status` — Create a commit status
- `get_blob` — Get a repository blob
- `get_tree` — Get a repository tree
- `repo_list_all_git_refs` — List all git refs
- `repo_list_git_refs` — List git refs matching a reference
- `get_annotated_tag` — Get an annotated tag object

### 📋 Issues (9 tools)

- `issue_search_issues` — Search for issues across the repositories that the user has access to
- `issue_list_issues` — List a repository's issues
- `issue_create_issue` — Create an issue
- `issue_get_issue` — Get an issue
- `issue_edit_issue` — Edit an issue
- `issue_delete` — Delete an issue
- `issue_add_assignees` — Add assignees to an issue
- `issue_remove_assignees` — Remove assignees from an issue
- `issue_check_assignee` — Check whether a user is assigned to an issue

### 💬 Issue Comments & Timeline (9 tools)

- `issue_get_repo_comments` — List issue comments across a repository
- `issue_get_comments` — List comments on an issue
- `issue_get_comment` — Get an issue comment by comment ID
- `issue_create_comment` — Create a comment on an issue
- `issue_edit_comment` — Edit a repository issue comment by comment ID
- `issue_delete_comment` — Delete a repository issue comment by comment ID
- `issue_edit_comment_deprecated` — Edit an issue comment by issue number and comment ID using the deprecated route
- `issue_delete_comment_deprecated` — Delete an issue comment by issue number and comment ID using the deprecated route
- `issue_get_comments_and_timeline` — List comments and timeline events for an issue

### 🏷️ Labels (15 tools)

- `org_list_labels` — List organization labels
- `org_create_label` — Create an organization label
- `org_delete_label` — Delete an organization label
- `org_get_label` — Get an organization label
- `org_edit_label` — Update an organization label
- `issue_clear_labels` — Remove all labels from an issue
- `issue_get_labels` — List labels on an issue
- `issue_add_label` — Add labels to an issue
- `issue_replace_labels` — Replace labels on an issue
- `issue_remove_label` — Remove a label from an issue
- `issue_list_labels` — List repository labels
- `issue_create_label` — Create a repository label
- `issue_delete_label` — Delete a repository label
- `issue_get_label` — Get a repository label
- `issue_edit_label` — Update a repository label

### 🎯 Milestones (5 tools)

- `issue_get_milestones_list` — Get all of a repository's opened milestones
- `issue_create_milestone` — Create a milestone
- `issue_delete_milestone` — Delete a milestone
- `issue_get_milestone` — Get a milestone
- `issue_edit_milestone` — Update a milestone

### 👍 Issue Reactions & Subscriptions (10 tools)

- `issue_delete_comment_reaction` — Remove a reaction from a comment of an issue
- `issue_get_comment_reactions` — Get a list of reactions from a comment of an issue
- `issue_post_comment_reaction` — Add a reaction to a comment of an issue
- `issue_delete_issue_reaction` — Remove a reaction from an issue
- `issue_get_issue_reactions` — Get a list reactions of an issue
- `issue_post_issue_reaction` — Add a reaction to an issue
- `issue_subscriptions` — Get users who subscribed on an issue
- `issue_check_subscription` — Check if user is subscribed to an issue
- `issue_delete_subscription` — Unsubscribe user from issue
- `issue_add_subscription` — Subscribe user to issue

### ⏱️ Time Tracking & Stopwatches (11 tools)

- `issue_reset_time` — Reset a tracked time of an issue
- `issue_tracked_times` — List an issue's tracked times
- `issue_add_time` — Add tracked time to a issue
- `issue_delete_time` — Delete specific tracked time
- `issue_delete_stop_watch` — Delete an issue's existing stopwatch
- `issue_start_stop_watch` — Start stopwatch on an issue
- `issue_stop_stop_watch` — Stop an issue's existing stopwatch
- `repo_tracked_times` — List a repo's tracked times
- `user_tracked_times` — List a user's tracked times in a repo
- `user_current_tracked_times` — List the current user's tracked times
- `user_get_stop_watches` — Get list of all existing stopwatches

### 🔗 Issue Relationships & Workflow (12 tools)

- `issue_remove_issue_blocking` — Unblock the issue given in the body by the issue in path
- `issue_list_blocks` — List issues that are blocked by this issue
- `issue_create_issue_blocking` — Block the issue given in the body by the issue in path
- `issue_edit_issue_deadline` — Set an issue deadline
- `issue_remove_issue_dependencies` — Remove an issue dependency
- `issue_list_issue_dependencies` — List an issue's dependencies, i.e all issues that block this issue
- `issue_create_issue_dependencies` — Make the issue in the url depend on the issue in the form
- `issue_unlock_issue` — Unlock an issue
- `issue_lock_issue` — Lock an issue
- `unpin_issue` — Unpin an Issue
- `pin_issue` — Pin an Issue
- `move_issue_pin` — Moves the Pin to the given Position

### 🔀 Pull Requests (12 tools)

- `repo_get_commit_pull_request` — Get the merged pull request of the commit
- `repo_list_pull_requests` — List a repo's pull requests
- `repo_create_pull_request` — Create a pull request
- `repo_get_pull_request_by_base_head` — Get a pull request by base and head
- `repo_get_pull_request` — Get a pull request
- `repo_edit_pull_request` — Update a pull request
- `repo_pull_request_is_merged` — Check if a pull request has been merged
- `repo_merge_pull_request` — Merge a pull request
- `repo_update_pull_request` — Merge PR's baseBranch into headBranch
- `repo_get_pull_request_commits` — Get commits for a pull request
- `repo_get_pull_request_files` — Get changed files for a pull request
- `repo_cancel_scheduled_auto_merge` — Cancel the scheduled auto merge for the given pull request

### 👀 Pull Request Reviews (13 tools)

- `repo_delete_pull_review_requests` — Cancel review requests for a pull request
- `repo_create_pull_review_requests` — Create review requests for a pull request
- `repo_list_pull_reviews` — List all reviews for a pull request
- `repo_create_pull_review` — Create a review to a pull request
- `repo_delete_pull_review` — Delete a specific review from a pull request
- `repo_get_pull_review` — Get a specific review for a pull request
- `repo_submit_pull_review` — Submit a pending review to a pull request
- `repo_get_pull_review_comments` — List comments for a specific pull request review
- `repo_dismiss_pull_review` — Dismiss a review for a pull request
- `repo_un_dismiss_pull_review` — Cancel to dismiss a review for a pull request
- `repo_resolve_pull_review_comment` — Resolve a pull request review comment
- `repo_unresolve_pull_review_comment` — Unresolve a pull request review comment
- `repo_create_pull_review_comment_reply` — Reply to a pull request review comment

### 🚀 Releases (8 tools)

- `repo_list_releases` — List a repo's releases
- `repo_create_release` — Create a release
- `repo_get_latest_release` — Get the most recent non-prerelease, non-draft release of a repository, sorted by created_at
- `repo_delete_release_by_tag` — Delete a release by tag name
- `repo_get_release_by_tag` — Get a release by tag name
- `repo_delete_release` — Delete a release
- `repo_get_release` — Get a release
- `repo_edit_release` — Update a release

### 📚 Wiki & Topics (11 tools)

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
- `topic_search` — Search topics via keyword

### 🔐 Branch & Tag Protection (11 tools)

- `repo_list_branch_protection` — List branch protections for a repository
- `repo_create_branch_protection` — Create a branch protections for a repository
- `repo_update_branch_protection_priorities` — Update the priorities of branch protections for a repository
- `repo_delete_branch_protection` — Delete a specific branch protection for the repository
- `repo_get_branch_protection` — Get a specific branch protection for the repository
- `repo_edit_branch_protection` — Edit a branch protections for a repository
- `repo_list_tag_protection` — List tag protections for a repository
- `repo_create_tag_protection` — Create a tag protections for a repository
- `repo_delete_tag_protection` — Delete a specific tag protection for the repository
- `repo_get_tag_protection` — Get a specific tag protection for the repository
- `repo_edit_tag_protection` — Edit a tag protections for a repository

### 👥 Collaborators, Keys & Repo Teams (14 tools)

- `repo_list_collaborators` — List a repository's collaborators
- `repo_delete_collaborator` — Delete a collaborator from a repository
- `repo_check_collaborator` — Check if a user is a collaborator of a repository
- `repo_add_collaborator` — Add or Update a collaborator to a repository
- `repo_get_repo_permissions` — Get repository permissions for a user
- `repo_list_keys` — List a repository's keys
- `repo_create_key` — Add a key to a repository
- `repo_delete_key` — Delete a key from a repository
- `repo_get_key` — Get a repository deploy key by ID
- `repo_create_deploy_token` — Add a deploy token to a repository, it authenticates git over HTTPS
- `repo_list_teams` — List teams assigned to a repository
- `repo_delete_team` — Remove a team from a repository
- `repo_check_team` — Check whether a team is assigned to a repository
- `repo_add_team` — Assign a team to a repository

### 🏢 Organizations (16 tools)

- `org_get_all` — Get list of organizations
- `org_create` — Create an organization
- `org_delete` — Delete an organization
- `org_get` — Get an organization
- `org_edit` — Edit an organization
- `org_list_activity_feeds` — List an organization's activity feeds
- `org_list_members` — List an organization's members
- `org_delete_member` — Remove a member from an organization
- `org_is_member` — Check if a user is a member of an organization
- `org_list_public_members` — List an organization's public members
- `org_conceal_member` — Conceal a user's membership
- `org_is_public_member` — Check if a user is a public member of an organization
- `org_publicize_member` — Publicize a user's membership
- `rename_org` — Rename an organization
- `org_list_repos` — List repositories in an organization
- `org_delete_repos` — Delete all repositories in an organization

### 👨‍👩‍👧‍👦 Teams (15 tools)

- `org_list_teams` — List teams in an organization
- `org_create_team` — Create a team in an organization
- `team_search` — Search for teams in an organization
- `org_delete_team` — Delete an organization team
- `org_get_team` — Get an organization team
- `org_edit_team` — Edit an organization team
- `org_list_team_activity_feeds` — List activity feeds for an organization team
- `org_list_team_members` — List members of an organization team
- `org_remove_team_member` — Remove a member from an organization team
- `org_list_team_member` — Get an organization team member
- `org_add_team_member` — Add a member to an organization team
- `org_list_team_repos` — List repositories assigned to an organization team
- `org_remove_team_repository` — Remove a repository from an organization team
- `org_list_team_repo` — Get a repository assigned to an organization team
- `org_add_team_repository` — Assign a repository to an organization team

### 👤 Users (19 tools)

- `user_get_current` — Get the authenticated user
- `user_current_list_followers` — List followers of the authenticated user
- `user_current_list_following` — List users followed by the authenticated user
- `user_current_delete_follow` — Unfollow a user
- `user_current_check_following` — Check whether a user is followed by the authenticated user
- `user_current_put_follow` — Follow a user
- `user_search` — Search for users
- `user_get` — Get a user by username
- `user_list_activity_feeds` — List activity feeds for a specified user
- `user_list_followers` — List followers of a specified user
- `user_list_following` — List users followed by a specified user
- `user_check_following` — Check if one user is following another user
- `user_list_gpg_keys` — List GPG keys for a specified user
- `user_get_heatmap_data` — Get contribution heatmap data for a specified user
- `user_list_keys` — List public SSH keys for a specified user
- `user_list_teams` — List teams for the authenticated user
- `org_list_current_user_orgs` — List organizations for the authenticated user
- `org_list_user_orgs` — List organizations for a specified user
- `org_get_user_permissions` — Get a user's permissions in an organization

### 📂 User Repositories & Subscriptions (9 tools)

- `user_current_list_repos` — List repositories owned by the authenticated user
- `user_list_repos` — List repositories owned by a specified user
- `user_current_list_starred` — List repositories starred by the authenticated user
- `user_list_starred` — List repositories starred by a specified user
- `user_current_list_subscriptions` — List repository subscriptions for the authenticated user
- `user_list_subscriptions` — List repository subscriptions for a specified user
- `user_current_check_subscription` — Check if the current user is watching a repo
- `user_current_put_subscription` — Watch a repo
- `user_current_delete_subscription` — Unwatch a repo

### 📊 Projects (49 tools)

- `org_list_projects` — List projects owned by an organization
- `org_create_project` — Create a project owned by an organization
- `org_delete_project` — Delete a project owned by an organization
- `org_get_project` — Get a project owned by an organization
- `org_edit_project` — Edit a project owned by an organization
- `org_list_project_columns` — List columns in an organization project
- `org_create_project_column` — Create a column in an organization project
- `org_move_project_columns` — Reorder columns in an organization project
- `org_delete_project_column` — Delete a column in an organization project
- `org_get_project_column` — Get a column in an organization project
- `org_edit_project_column` — Edit a column in an organization project
- `org_set_default_project_column` — Set the default column for an organization project
- `org_list_project_column_issues` — List issues in an organization project column
- `org_remove_issue_from_project_column` — Remove an issue from an organization project column
- `org_add_issue_to_project_column` — Add an issue to an organization project column
- `org_move_project_issue` — Move an issue between columns in an organization project
- `repo_list_projects` — List projects owned by a repository
- `repo_create_project` — Create a project owned by a repository
- `repo_delete_project` — Delete a project owned by a repository
- `repo_get_project` — Get a project owned by a repository
- `repo_edit_project` — Edit a project owned by a repository
- `repo_list_project_columns` — List columns in a repository project
- `repo_create_project_column` — Create a column in a repository project
- `repo_move_project_columns` — Reorder columns in a repository project
- `repo_delete_project_column` — Delete a column in a repository project
- `repo_get_project_column` — Get a column in a repository project
- `repo_edit_project_column` — Edit a column in a repository project
- `repo_set_default_project_column` — Set the default column for a repository project
- `repo_list_project_column_issues` — List issues in a repository project column
- `repo_remove_issue_from_project_column` — Remove an issue from a repository project column
- `repo_add_issue_to_project_column` — Add an issue to a repository project column
- `repo_move_project_issue` — Move an issue between columns in a repository project
- `user_current_list_projects` — List projects owned by the authenticated user
- `user_current_create_project` — Create a project owned by the authenticated user
- `user_current_delete_project` — Delete a project owned by the authenticated user
- `user_current_get_project` — Get a project owned by the authenticated user
- `user_current_edit_project` — Edit a project owned by the authenticated user
- `user_current_list_project_columns` — List columns in the authenticated user's project
- `user_current_create_project_column` — Create a column in the authenticated user's project
- `user_current_move_project_columns` — Reorder columns in the authenticated user's project
- `user_current_delete_project_column` — Delete a column in the authenticated user's project
- `user_current_get_project_column` — Get a column in the authenticated user's project
- `user_current_edit_project_column` — Edit a column in the authenticated user's project
- `user_current_set_default_project_column` — Set the default column for the authenticated user's project
- `user_current_list_project_column_issues` — List issues in the authenticated user's project column
- `user_current_remove_issue_from_project_column` — Remove an issue from the authenticated user's project column
- `user_current_add_issue_to_project_column` — Add an issue to the authenticated user's project column
- `user_current_move_project_issue` — Move an issue between columns in the authenticated user's project
- `user_list_projects` — List projects owned by a specified user

### 🔔 Notifications (7 tools)

- `notify_get_list` — List notification threads for the authenticated user
- `notify_read_list` — Mark notification threads as read, pinned, or unread
- `notify_new_available` — Check if unread notifications exist
- `notify_get_thread` — Get notification thread by ID
- `notify_read_thread` — Mark notification thread as read by ID
- `notify_get_repo_list` — List notification threads for a repository
- `notify_read_repo_list` — Mark repository notification threads as read, pinned, or unread

### 📦 Packages (10 tools)

- `list_packages` — List all packages for an owner
- `list_package_versions` — List all versions of a package
- `get_latest_package_version` — Get the latest version of a package
- `link_package` — Link a package to a repository
- `unlink_package` — Unlink a package from a repository
- `delete_package` — Delete a package
- `delete_package_version` — Delete a package version
- `get_package` — Get a package
- `list_package_files` — List all files of a package
- `upload_generic_package` — Upload a text file as a Gitea generic package
