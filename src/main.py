from __future__ import annotations

import json
import os
import sys
from contextvars import ContextVar
from typing import Any, Literal, Optional

from fastmcp import FastMCP, Context
from mcp.types import ToolAnnotations
from pydantic import BaseModel, Field
from toon_mcp import json_to_toon

from .client import GiteaClient

_current_user_token: ContextVar[Optional[str]] = ContextVar("current_user_token", default=None)

ALLOW_ALL_AGGREGATE = os.getenv("ALLOW_ALL_AGGREGATE", "false").lower() in ("true", "1", "yes")
IS_STATEFUL = os.getenv("IS_STATEFUL", "false").lower() in ("true", "1", "yes")


class AuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = dict(scope.get("headers", []))
            auth_header = headers.get(b"authorization", b"").decode()
            if auth_header.startswith("Bearer ") or auth_header.startswith("Token "):
                token = auth_header.split(" ", 1)[1]
                _current_user_token.set(token)
        await self.app(scope, receive, send)


mcp = FastMCP("Gitea MCP Server")

_client: Optional[GiteaClient] = None


def get_client() -> GiteaClient:
    global _client
    if _client is None:
        _client = GiteaClient()
    return _client


def get_user_token() -> Optional[str]:
    return _current_user_token.get()


# =============================================================================
# Pydantic Contract Models
# =============================================================================

class CreateBranchProtectionOption(BaseModel):
    approvals_whitelist_teams: Optional[list[str]] = Field(default=None, description='')
    approvals_whitelist_username: Optional[list[str]] = Field(default=None, description='')
    block_admin_merge_override: bool = Field(default=False, description='')
    block_on_official_review_requests: bool = Field(default=False, description='')
    block_on_outdated_branch: bool = Field(default=False, description='')
    block_on_rejected_reviews: bool = Field(default=False, description='')
    branch_name: str = Field(default='', description='Deprecated: true')
    dismiss_stale_approvals: bool = Field(default=False, description='')
    enable_approvals_whitelist: bool = Field(default=False, description='')
    enable_force_push: bool = Field(default=False, description='')
    enable_force_push_allowlist: bool = Field(default=False, description='')
    enable_merge_whitelist: bool = Field(default=False, description='')
    enable_push: bool = Field(default=False, description='')
    enable_push_whitelist: bool = Field(default=False, description='')
    enable_status_check: bool = Field(default=False, description='')
    force_push_allowlist_deploy_keys: bool = Field(default=False, description='')
    force_push_allowlist_teams: Optional[list[str]] = Field(default=None, description='')
    force_push_allowlist_usernames: Optional[list[str]] = Field(default=None, description='')
    ignore_stale_approvals: bool = Field(default=False, description='')
    merge_whitelist_teams: Optional[list[str]] = Field(default=None, description='')
    merge_whitelist_usernames: Optional[list[str]] = Field(default=None, description='')
    priority: int = Field(default=0, description='')
    protected_file_patterns: str = Field(default='', description='')
    push_whitelist_deploy_keys: bool = Field(default=False, description='')
    push_whitelist_teams: Optional[list[str]] = Field(default=None, description='')
    push_whitelist_usernames: Optional[list[str]] = Field(default=None, description='')
    require_signed_commits: bool = Field(default=False, description='')
    required_approvals: int = Field(default=0, description='')
    rule_name: str = Field(default='', description='')
    status_check_contexts: Optional[list[str]] = Field(default=None, description='')
    unprotected_file_patterns: str = Field(default='', description='')

class EditMilestoneOption(BaseModel):
    description: str = Field(default='', description='Description provides updated details about the milestone')
    due_on: str = Field(default='', description='Deadline is the updated due date for the milestone')
    state: str = Field(default='', description='State indicates the updated state of the milestone')
    title: str = Field(default='', description='Title is the updated title of the milestone')

class InternalTracker(BaseModel):
    allow_only_contributors_to_track_time: bool = Field(default=False, description='Let only contributors track time (Built-in issue tracker)')
    enable_issue_dependencies: bool = Field(default=False, description='Enable dependencies for issues and pull requests (Built-in issue tracker)')
    enable_time_tracker: bool = Field(default=False, description='Enable time tracking (Built-in issue tracker)')

class ExternalTracker(BaseModel):
    external_tracker_format: str = Field(default='', description='External Issue Tracker URL Format. Use the placeholders {user}, {repo} and {index} for the username, repository name and issue index.')
    external_tracker_regexp_pattern: str = Field(default='', description='External Issue Tracker issue regular expression')
    external_tracker_style: str = Field(default='', description='External Issue Tracker Number Format, either `numeric`, `alphanumeric`, or `regexp`')
    external_tracker_url: str = Field(default='', description='URL of external issue tracker.')

class UpdateBranchProtectionPriories(BaseModel):
    ids: Optional[list[int]] = Field(default=None, description='')

class MigrateRepoOptions(BaseModel):
    auth_password: str = Field(default='', description='')
    auth_token: str = Field(default='', description='')
    auth_username: str = Field(default='', description='')
    aws_access_key_id: str = Field(default='', description='')
    aws_secret_access_key: str = Field(default='', description='')
    clone_addr: str = Field(..., description='')
    description: str = Field(default='', description='')
    issues: bool = Field(default=False, description='')
    labels: bool = Field(default=False, description='')
    lfs: bool = Field(default=False, description='')
    lfs_endpoint: str = Field(default='', description='')
    milestones: bool = Field(default=False, description='')
    mirror: bool = Field(default=False, description='')
    mirror_interval: str = Field(default='', description='')
    private: bool = Field(default=False, description='')
    pull_requests: bool = Field(default=False, description='')
    releases: bool = Field(default=False, description='')
    repo_name: str = Field(..., description='')
    repo_owner: str = Field(default='', description="the organization's name or individual user's name who will own the migrated repository")
    service: Optional[Literal['git', 'github', 'gitea', 'gitlab', 'gogs', 'onedev', 'gitbucket', 'codebase', 'codecommit']] = Field(default='git', description='')
    uid: int = Field(default=0, description='deprecated (only for backwards compatibility, use repo_owner instead)')
    wiki: bool = Field(default=False, description='')

class CreateStatusOption(BaseModel):
    context: str = Field(default='', description='Context is the unique context identifier for the status')
    description: str = Field(default='', description='Description provides a brief description of the status')
    state: Optional[Literal['pending', 'success', 'error', 'failure', 'warning', 'skipped']] = Field(default='pending', description='State represents the status state to set (pending, success, error, failure) pending CommitStatusPending  CommitStatusPending is for when the CommitStatus is Pending success CommitStatusSuccess  CommitStatusSuccess is for when the CommitStatus is Success error CommitStatusError  CommitStatusError is for when the CommitStatus is Error failure CommitStatusFailure  CommitStatusFailure is for when the CommitStatus is Failure warning CommitStatusWarning  CommitStatusWarning is for when the CommitStatus is Warning skipped CommitStatusSkipped  CommitStatusSkipped is for when CommitStatus is Skipped')
    target_url: str = Field(default='', description='TargetURL is the URL to link to for more details')

class RepoTopicOptions(BaseModel):
    topics: Optional[list[str]] = Field(default=None, description='list of topic names')

class CreatePullReviewComment(BaseModel):
    body: str = Field(default='', description='')
    new_position: int = Field(default=0, description='if comment to new file line or 0')
    old_position: int = Field(default=0, description='if comment to old file line or 0')
    path: str = Field(default='', description='the tree path')

class CreateReleaseOption(BaseModel):
    body: str = Field(default='', description='The release notes or description')
    draft: bool = Field(default=False, description='Whether to create the release as a draft')
    name: str = Field(default='', description='The display title of the release')
    prerelease: bool = Field(default=False, description='Whether to mark the release as a prerelease')
    tag_message: str = Field(default='', description='The message for the git tag')
    tag_name: str = Field(..., description='')
    target_commitish: str = Field(default='', description='The target commitish for the release')

class AddCollaboratorOption(BaseModel):
    permission: Optional[Literal['read', 'write', 'admin']] = Field(default='read', description='')

class AddTimeOption(BaseModel):
    created: str = Field(default='', description='')
    time: int = Field(..., description='time in seconds')
    user_name: str = Field(default='', description='username of the user who spent the time working on the issue (optional)')

class EditTeamOption(BaseModel):
    can_create_org_repo: bool = Field(default=False, description='Whether the team can create repositories in the organization')
    description: str = Field(default='', description='The description of the team')
    includes_all_repositories: bool = Field(default=False, description='Whether the team has access to all repositories in the organization')
    name: str = Field(..., description='')
    permission: Optional[Literal['read', 'write', 'admin']] = Field(default='read', description='')
    units: Optional[list[str]] = Field(default=None, description='')

class CreateTagProtectionOption(BaseModel):
    name_pattern: str = Field(default='', description='The pattern to match tag names for protection')
    whitelist_teams: Optional[list[str]] = Field(default=None, description='List of team names allowed to create/delete protected tags')
    whitelist_usernames: Optional[list[str]] = Field(default=None, description='List of usernames allowed to create/delete protected tags')

class DismissPullReviewOptions(BaseModel):
    message: str = Field(default='', description='')
    priors: bool = Field(default=False, description='')

class ExternalWiki(BaseModel):
    external_wiki_url: str = Field(default='', description='URL of external wiki.')

class EditIssueCommentOption(BaseModel):
    body: str = Field(..., description='')

class CreateForkOption(BaseModel):
    name: str = Field(default='', description='name of the forked repository')
    organization: str = Field(default='', description='organization name, if forking into an organization')

class CreatePullRequestOption(BaseModel):
    assignee: str = Field(default='', description='The primary assignee username')
    assignees: Optional[list[str]] = Field(default=None, description='The list of assignee usernames')
    base: str = Field(default='', description='The base branch for the pull request')
    body: str = Field(default='', description='The description body of the pull request')
    due_date: str = Field(default='', description='')
    head: str = Field(default='', description="The head branch for the pull request, it could be a branch name on the base repository or a form like `<username>:<branch>` which refers to the user's fork repository's branch.")
    labels: Optional[list[int]] = Field(default=None, description='The list of label IDs to assign to the pull request')
    milestone: int = Field(default=0, description='The milestone ID to assign to the pull request')
    reviewers: Optional[list[str]] = Field(default=None, description='The list of reviewer usernames')
    team_reviewers: Optional[list[str]] = Field(default=None, description='The list of team reviewer names')
    title: str = Field(default='', description='The title of the pull request')

class CreateOrgOption(BaseModel):
    description: str = Field(default='', description='The description of the organization')
    email: str = Field(default='', description='The email address of the organization')
    full_name: str = Field(default='', description='The full display name of the organization')
    location: str = Field(default='', description='The location of the organization')
    repo_admin_change_team_access: bool = Field(default=False, description='Whether repository administrators can change team access')
    username: str = Field(..., description='username of the organization')
    visibility: Optional[Literal['public', 'limited', 'private']] = Field(default='public', description='possible values are `public` (default), `limited` or `private`')
    website: str = Field(default='', description='The website URL of the organization')

class EditLabelOption(BaseModel):
    color: str = Field(default='', description='')
    description: str = Field(default='', description="Description provides additional context about the label's purpose")
    exclusive: bool = Field(default=False, description='')
    is_archived: bool = Field(default=False, description='')
    name: str = Field(default='', description='Name is the new display name for the label')

class EditBranchProtectionOption(BaseModel):
    approvals_whitelist_teams: Optional[list[str]] = Field(default=None, description='')
    approvals_whitelist_username: Optional[list[str]] = Field(default=None, description='')
    block_admin_merge_override: bool = Field(default=False, description='')
    block_on_official_review_requests: bool = Field(default=False, description='')
    block_on_outdated_branch: bool = Field(default=False, description='')
    block_on_rejected_reviews: bool = Field(default=False, description='')
    dismiss_stale_approvals: bool = Field(default=False, description='')
    enable_approvals_whitelist: bool = Field(default=False, description='')
    enable_force_push: bool = Field(default=False, description='')
    enable_force_push_allowlist: bool = Field(default=False, description='')
    enable_merge_whitelist: bool = Field(default=False, description='')
    enable_push: bool = Field(default=False, description='')
    enable_push_whitelist: bool = Field(default=False, description='')
    enable_status_check: bool = Field(default=False, description='')
    force_push_allowlist_deploy_keys: bool = Field(default=False, description='')
    force_push_allowlist_teams: Optional[list[str]] = Field(default=None, description='')
    force_push_allowlist_usernames: Optional[list[str]] = Field(default=None, description='')
    ignore_stale_approvals: bool = Field(default=False, description='')
    merge_whitelist_teams: Optional[list[str]] = Field(default=None, description='')
    merge_whitelist_usernames: Optional[list[str]] = Field(default=None, description='')
    priority: int = Field(default=0, description='')
    protected_file_patterns: str = Field(default='', description='')
    push_whitelist_deploy_keys: bool = Field(default=False, description='')
    push_whitelist_teams: Optional[list[str]] = Field(default=None, description='')
    push_whitelist_usernames: Optional[list[str]] = Field(default=None, description='')
    require_signed_commits: bool = Field(default=False, description='')
    required_approvals: int = Field(default=0, description='')
    status_check_contexts: Optional[list[str]] = Field(default=None, description='')
    unprotected_file_patterns: str = Field(default='', description='')

class CreateTeamOption(BaseModel):
    can_create_org_repo: bool = Field(default=False, description='Whether the team can create repositories in the organization')
    description: str = Field(default='', description='The description of the team')
    includes_all_repositories: bool = Field(default=False, description='Whether the team has access to all repositories in the organization')
    name: str = Field(..., description='')
    permission: Optional[Literal['read', 'write', 'admin']] = Field(default='read', description='')
    units: Optional[list[str]] = Field(default=None, description='')

class MergeUpstreamRequest(BaseModel):
    branch: str = Field(default='', description='')
    ff_only: bool = Field(default=False, description='')

class CreateLabelOption(BaseModel):
    color: str = Field(..., description='')
    description: str = Field(default='', description="Description provides additional context about the label's purpose")
    exclusive: bool = Field(default=False, description='')
    is_archived: bool = Field(default=False, description='')
    name: str = Field(..., description='')

class CreateTagOption(BaseModel):
    message: str = Field(default='', description='The message to associate with the tag')
    tag_name: str = Field(..., description='')
    target: str = Field(default='', description='The target commit SHA or branch name for the tag')

class CreateKeyOption(BaseModel):
    key: str = Field(..., description='An armored SSH key to add')
    read_only: bool = Field(default=False, description='Describe if the key has only read access or read/write')
    title: str = Field(..., description='Title of the key to add')

class EditPullRequestOption(BaseModel):
    allow_maintainer_edit: bool = Field(default=False, description='Whether to allow maintainer edits')
    assignee: str = Field(default='', description='The new primary assignee username')
    assignees: Optional[list[str]] = Field(default=None, description='The new list of assignee usernames')
    base: str = Field(default='', description='The new base branch for the pull request')
    body: str = Field(default='', description='The new description body for the pull request')
    due_date: str = Field(default='', description='')
    labels: Optional[list[int]] = Field(default=None, description='The new list of label IDs for the pull request')
    milestone: int = Field(default=0, description='The new milestone ID for the pull request')
    state: str = Field(default='', description='The new state for the pull request')
    title: str = Field(default='', description='The new title for the pull request')
    unset_due_date: bool = Field(default=False, description='Whether to remove the current deadline')

class GenerateRepoOption(BaseModel):
    avatar: bool = Field(default=False, description='include avatar of the template repo')
    default_branch: str = Field(default='', description='Default branch of the new repository')
    description: str = Field(default='', description='Description of the repository to create')
    git_content: bool = Field(default=False, description='include git content of default branch in template repo')
    git_hooks: bool = Field(default=False, description='include git hooks in template repo')
    labels: bool = Field(default=False, description='include labels in template repo')
    name: str = Field(..., description='')
    owner: str = Field(..., description="the organization's name or individual user's name who will own the new repository")
    private: bool = Field(default=False, description='Whether the repository is private')
    protected_branch: bool = Field(default=False, description='include protected branches in template repo')
    topics: bool = Field(default=False, description='include topics in template repo')
    webhooks: bool = Field(default=False, description='include webhooks in template repo')

class CreateRepoOption(BaseModel):
    auto_init: bool = Field(default=False, description='Whether the repository should be auto-initialized?')
    default_branch: str = Field(default='', description='DefaultBranch of the repository (used when initializes and in template)')
    description: str = Field(default='', description='Description of the repository to create')
    gitignores: str = Field(default='', description='Gitignores to use')
    issue_labels: str = Field(default='', description='Label-Set to use')
    license: str = Field(default='', description='License to use')
    name: str = Field(..., description='Name of the repository to create')
    object_format_name: Optional[Literal['sha1', 'sha256']] = Field(default='sha1', description='ObjectFormatName of the underlying git repository')
    private: bool = Field(default=False, description='Whether the repository is private')
    readme: str = Field(default='', description='Readme of the repository to create')
    template: bool = Field(default=False, description='Whether the repository is template')
    trust_model: Optional[Literal['default', 'collaborator', 'committer', 'collaboratorcommitter']] = Field(default='default', description='TrustModel of the repository')

class CreateIssueCommentOption(BaseModel):
    body: str = Field(..., description='')

class Identity(BaseModel):
    email: str = Field(default='', description='')
    name: str = Field(default='', description="Name is the person's name")

class ChangeFileOperation(BaseModel):
    content: str = Field(default='', description='new or updated file content, it must be base64 encoded')
    from_path: str = Field(default='', description='old path of the file to move')
    operation: Literal['create', 'update', 'upload', 'rename', 'delete'] = Field(..., description='indicates what to do with the file: "create" for creating a new file, "update" for updating an existing file, "upload" for creating or updating a file, "rename" for renaming a file, and "delete" for deleting an existing file.')
    path: str = Field(..., description='path to the existing or new file')
    sha: str = Field(default='', description='the blob ID (SHA) for the file that already exists, required for changing existing files')

class CreateMilestoneOption(BaseModel):
    description: str = Field(default='', description='Description provides details about the milestone')
    due_on: str = Field(default='', description='')
    state: Optional[Literal['open', 'closed']] = Field(default='open', description='')
    title: str = Field(default='', description='Title is the title of the new milestone')

class EditReactionOption(BaseModel):
    content: str = Field(default='', description='The reaction content (e.g., emoji or reaction type)')

class IssueLabelsOption(BaseModel):
    labels: Optional[list[Any]] = Field(default=None, description='Labels can be a list of integers representing label IDs or a list of strings representing label names')

class PullReviewRequestOptions(BaseModel):
    reviewers: Optional[list[str]] = Field(default=None, description='')
    team_reviewers: Optional[list[str]] = Field(default=None, description='')

class RenameBranchRepoOption(BaseModel):
    name: str = Field(..., description='New branch name')

class EditDeadlineOption(BaseModel):
    due_date: str = Field(..., description='')

class EditTagProtectionOption(BaseModel):
    name_pattern: str = Field(default='', description='The pattern to match tag names for protection')
    whitelist_teams: Optional[list[str]] = Field(default=None, description='List of team names allowed to create/delete protected tags')
    whitelist_usernames: Optional[list[str]] = Field(default=None, description='List of usernames allowed to create/delete protected tags')

class RenameOrgOption(BaseModel):
    new_name: str = Field(..., description='New username for this org. This name cannot be in use yet by any other user.')

class LockIssueOption(BaseModel):
    lock_reason: str = Field(default='', description='')

class IssueMeta(BaseModel):
    index: int = Field(default=0, description='')
    owner: str = Field(default='', description="owner of the issue's repo")
    repo: str = Field(default='', description='')

class EditReleaseOption(BaseModel):
    body: str = Field(default='', description='The new release notes or description')
    draft: bool = Field(default=False, description='Whether to change the draft status')
    name: str = Field(default='', description='The new display title of the release')
    prerelease: bool = Field(default=False, description='Whether to change the prerelease status')
    tag_name: str = Field(default='', description='The new name of the git tag')
    target_commitish: str = Field(default='', description='The new target commitish for the release')

class EditOrgOption(BaseModel):
    description: str = Field(default='', description='The description of the organization')
    email: str = Field(default='', description='The email address of the organization')
    full_name: str = Field(default='', description='The full display name of the organization')
    location: str = Field(default='', description='The location of the organization')
    repo_admin_change_team_access: bool = Field(default=False, description='Whether repository administrators can change team access')
    visibility: Optional[Literal['public', 'limited', 'private']] = Field(default='public', description='possible values are `public`, `limited` or `private`')
    website: str = Field(default='', description='The website URL of the organization')

class CreateWikiPageOptions(BaseModel):
    content_base64: str = Field(default='', description='content must be base64 encoded')
    message: str = Field(default='', description='optional commit message summarizing the change')
    title: str = Field(default='', description='page title. leave empty to keep unchanged')

class CreateIssueOption(BaseModel):
    assignee: str = Field(default='', description='deprecated')
    assignees: Optional[list[str]] = Field(default=None, description='')
    body: str = Field(default='', description='')
    closed: bool = Field(default=False, description='')
    due_date: str = Field(default='', description='')
    labels: Optional[list[int]] = Field(default=None, description='list of label ids')
    milestone: int = Field(default=0, description='milestone id')
    ref: str = Field(default='', description='')
    title: str = Field(..., description='')

class MergePullRequestOption(BaseModel):
    Do: Literal['merge', 'rebase', 'rebase-merge', 'squash', 'fast-forward-only', 'manually-merged'] = Field(..., description='')
    MergeCommitID: str = Field(default='', description='')
    MergeMessageField: str = Field(default='', description='')
    MergeTitleField: str = Field(default='', description='')
    delete_branch_after_merge: bool = Field(default=False, description='')
    force_merge: bool = Field(default=False, description='')
    head_commit_id: str = Field(default='', description='')
    merge_when_checks_succeed: bool = Field(default=False, description='')

class CommitDateOptions(BaseModel):
    author: str = Field(default='', description='')
    committer: str = Field(default='', description='')

class ApplyDiffPatchFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used')
    committer: Optional[Identity] = Field(default=None, description='')
    content: str = Field(..., description='')
    dates: Optional[CommitDateOptions] = Field(default=None, description='')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class CreateBranchRepoOption(BaseModel):
    new_branch_name: str = Field(..., description='Name of the branch to create')
    old_branch_name: str = Field(default='', description='Deprecated: true Name of the old branch to create from')
    old_ref_name: str = Field(default='', description='Name of the old branch/tag/commit to create from')

class EditIssueOption(BaseModel):
    assignee: str = Field(default='', description='deprecated')
    assignees: Optional[list[str]] = Field(default=None, description='')
    body: str = Field(default='', description='')
    due_date: str = Field(default='', description='')
    milestone: int = Field(default=0, description='')
    ref: str = Field(default='', description='')
    state: str = Field(default='', description='')
    title: str = Field(default='', description='')
    unset_due_date: bool = Field(default=False, description='')

class EditRepoOption(BaseModel):
    allow_fast_forward_only_merge: bool = Field(default=False, description='either `true` to allow fast-forward-only merging pull requests, or `false` to prevent fast-forward-only merging.')
    allow_manual_merge: bool = Field(default=False, description='either `true` to allow mark pr as merged manually, or `false` to prevent it.')
    allow_merge_commits: bool = Field(default=False, description='either `true` to allow merging pull requests with a merge commit, or `false` to prevent merging pull requests with merge commits.')
    allow_rebase: bool = Field(default=False, description='either `true` to allow rebase-merging pull requests, or `false` to prevent rebase-merging.')
    allow_rebase_explicit: bool = Field(default=False, description='either `true` to allow rebase with explicit merge commits (--no-ff), or `false` to prevent rebase with explicit merge commits.')
    allow_rebase_update: bool = Field(default=False, description='either `true` to allow updating pull request branch by rebase, or `false` to prevent it.')
    allow_squash_merge: bool = Field(default=False, description='either `true` to allow squash-merging pull requests, or `false` to prevent squash-merging.')
    archived: bool = Field(default=False, description='set to `true` to archive this repository.')
    autodetect_manual_merge: bool = Field(default=False, description='either `true` to enable AutodetectManualMerge, or `false` to prevent it. Note: In some special cases, misjudgments can occur.')
    default_allow_maintainer_edit: bool = Field(default=False, description='set to `true` to allow edits from maintainers by default')
    default_branch: str = Field(default='', description='sets the default branch for this repository.')
    default_delete_branch_after_merge: bool = Field(default=False, description='set to `true` to delete pr branch after merge by default')
    default_merge_style: str = Field(default='', description='set to a merge style to be used by this repository: "merge", "rebase", "rebase-merge", "squash", or "fast-forward-only".')
    description: str = Field(default='', description='a short description of the repository.')
    enable_prune: bool = Field(default=False, description='enable prune - remove obsolete remote-tracking references when mirroring')
    external_tracker: Optional[ExternalTracker] = Field(default=None, description='')
    external_wiki: Optional[ExternalWiki] = Field(default=None, description='')
    has_actions: bool = Field(default=False, description='either `true` to enable actions unit, or `false` to disable them.')
    has_code: bool = Field(default=False, description='either `true` to enable code for this repository or `false` to disable it.')
    has_issues: bool = Field(default=False, description='either `true` to enable issues for this repository or `false` to disable them.')
    has_packages: bool = Field(default=False, description='either `true` to enable packages unit, or `false` to disable them.')
    has_projects: bool = Field(default=False, description='either `true` to enable project unit, or `false` to disable them.')
    has_pull_requests: bool = Field(default=False, description='either `true` to allow pull requests, or `false` to prevent pull request.')
    has_releases: bool = Field(default=False, description='either `true` to enable releases unit, or `false` to disable them.')
    has_wiki: bool = Field(default=False, description='either `true` to enable the wiki for this repository or `false` to disable it.')
    ignore_whitespace_conflicts: bool = Field(default=False, description='either `true` to ignore whitespace for conflicts, or `false` to not ignore whitespace.')
    internal_tracker: Optional[InternalTracker] = Field(default=None, description='')
    mirror_interval: str = Field(default='', description='set to a string like `8h30m0s` to set the mirror interval time')
    name: str = Field(default='', description='name of the repository')
    private: bool = Field(default=False, description='either `true` to make the repository private or `false` to make it public. Note: you will get a 422 error if the organization restricts changing repository visibility to organization owners and a non-owner tries to change the value of private.')
    projects_mode: str = Field(default='', description='`repo` to only allow repo-level projects, `owner` to only allow owner projects, `all` to allow both.')
    template: bool = Field(default=False, description='either `true` to make this repository a template or `false` to make it a normal repository')
    website: str = Field(default='', description='a URL with more information about the repository.')

class CreateFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used')
    committer: Optional[Identity] = Field(default=None, description='')
    content: str = Field(..., description='content must be base64 encoded')
    dates: Optional[CommitDateOptions] = Field(default=None, description='')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class DeleteFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used')
    committer: Optional[Identity] = Field(default=None, description='')
    dates: Optional[CommitDateOptions] = Field(default=None, description='')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file')
    sha: str = Field(..., description='the blob ID (SHA) for the file that already exists, it is required for changing existing files')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class ChangeFilesOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used')
    committer: Optional[Identity] = Field(default=None, description='')
    dates: Optional[CommitDateOptions] = Field(default=None, description='')
    files: list[ChangeFileOperation] = Field(..., description='list of file operations')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class UpdateFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used')
    committer: Optional[Identity] = Field(default=None, description='')
    content: str = Field(..., description='content must be base64 encoded')
    dates: Optional[CommitDateOptions] = Field(default=None, description='')
    from_path: str = Field(default='', description='from_path (optional) is the path of the original file which will be moved/renamed to the path in the URL')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file')
    sha: str = Field(..., description='the blob ID (SHA) for the file that already exists, it is required for changing existing files')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class SubmitPullReviewOptions(BaseModel):
    body: str = Field(default='', description='')
    event: str = Field(default=None, description='')

class CreatePullReviewOptions(BaseModel):
    body: str = Field(default='', description='')
    comments: Optional[list[CreatePullReviewComment]] = Field(default=None, description='')
    commit_id: str = Field(default='', description='')
    event: str = Field(default=None, description='')


# =============================================================================
# Tools
# =============================================================================

@mcp.tool(
    name='notify_get_list',
    description="List users's notification threads",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_get_list(all: bool = False, status_types: Optional[list[str]] = None, subject_type: Optional[list[Literal['issue', 'pull', 'commit', 'repository']]] = None, since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List users's notification threads

    Args:
        all: If true, show notifications marked as read. Default value is false
        status_types: Show notifications with the provided status types. Options are: unread, read and/or pinned. Defaults to unread & pinned.
        subject_type: filter notifications by subject type
        since: Only show notifications updated after the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show notifications updated before the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status-types'] = status_types
    if subject_type is not None and subject_type != "": args['subject-type'] = subject_type
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_get_list', get_user_token(), **args)
    return {'notifications': json_to_toon(data)}

@mcp.tool(
    name='notify_read_list',
    description='Mark notification threads as read, pinned or unread',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_read_list(last_read_at: str = "", all: str = "", status_types: Optional[list[str]] = None, to_status: str = "", sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Mark notification threads as read, pinned or unread

    Args:
        last_read_at: Describes the last point that notifications were checked. Anything updated since this time will not be updated. ISO 8601 format (2026-06-22T15:00:00-04:00).
        all: If true, mark all notifications on this repo. Default value is false
        status_types: Mark notifications with the provided status types. Options are: unread, read and/or pinned. Defaults to unread.
        to_status: Status to mark notifications as, Defaults to read.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if last_read_at is not None and last_read_at != "": args['last_read_at'] = last_read_at
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status-types'] = status_types
    if to_status is not None and to_status != "": args['to-status'] = to_status
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_read_list', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='notify_new_available',
    description='Check if unread notifications exist',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_new_available(include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if unread notifications exist

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_new_available', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='notify_get_thread',
    description='Get notification thread by ID',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_get_thread(id: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get notification thread by ID

    Args:
        id: id of notification thread
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_get_thread', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='notify_read_thread',
    description='Mark notification thread as read by ID',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_read_thread(id: str, to_status: str = 'read', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Mark notification thread as read by ID

    Args:
        id: id of notification thread
        to_status: Status to mark notifications as
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if to_status is not None and to_status != "": args['to-status'] = to_status
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_read_thread', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='create_org_repo_deprecated',
    description='Create a repository in an organization',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def create_org_repo_deprecated(org: str, description: str, name: str, auto_init: bool = False, default_branch: str = '', gitignores: str = '', issue_labels: str = '', license: str = '', object_format_name: Optional[Literal['sha1', 'sha256']] = 'sha1', private: bool = False, readme: str = '', template: bool = False, trust_model: Optional[Literal['default', 'collaborator', 'committer', 'collaboratorcommitter']] = 'default', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository in an organization

    Args:
        org: name of organization
        auto_init: Whether the repository should be auto-initialized?
        default_branch: DefaultBranch of the repository (used when initializes and in template)
        description: Description of the repository to create
        gitignores: Gitignores to use
        issue_labels: Label-Set to use
        license: License to use
        name: Name of the repository to create
        object_format_name: ObjectFormatName of the underlying git repository
        private: Whether the repository is private
        readme: Readme of the repository to create
        template: Whether the repository is template
        trust_model: TrustModel of the repository
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if auto_init: args['auto_init'] = auto_init
    if default_branch != "": args['default_branch'] = default_branch
    args['description'] = description
    if gitignores != "": args['gitignores'] = gitignores
    if issue_labels != "": args['issue_labels'] = issue_labels
    if license != "": args['license'] = license
    args['name'] = name
    if object_format_name is not None: args['object_format_name'] = object_format_name
    if private: args['private'] = private
    if readme != "": args['readme'] = readme
    if template: args['template'] = template
    if trust_model is not None: args['trust_model'] = trust_model
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_org_repo_deprecated', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_get_all',
    description='Get list of organizations',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_get_all(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get list of organizations

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get_all', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='org_create',
    description='Create an organization',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def org_create(description: str, username: str, email: str = '', full_name: str = '', location: str = '', repo_admin_change_team_access: bool = False, visibility: Optional[Literal['public', 'limited', 'private']] = 'public', website: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create an organization

    Args:
        description: The description of the organization
        email: The email address of the organization
        full_name: The full display name of the organization
        location: The location of the organization
        repo_admin_change_team_access: Whether repository administrators can change team access
        username: username of the organization
        visibility: possible values are `public` (default), `limited` or `private`
        website: The website URL of the organization
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['description'] = description
    if email != "": args['email'] = email
    if full_name != "": args['full_name'] = full_name
    if location != "": args['location'] = location
    if repo_admin_change_team_access: args['repo_admin_change_team_access'] = repo_admin_change_team_access
    args['username'] = username
    if visibility is not None: args['visibility'] = visibility
    if website != "": args['website'] = website
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_create', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_delete',
    description='Delete an organization',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_delete(org: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete an organization

    Args:
        org: organization that is to be deleted
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_get',
    description='Get an organization',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_get(org: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get an organization

    Args:
        org: name of the organization to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_edit',
    description='Edit an organization',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_edit(org: str, description: str = '', email: str = '', full_name: str = '', location: str = '', repo_admin_change_team_access: bool = False, visibility: Optional[Literal['public', 'limited', 'private']] = 'public', website: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit an organization

    Args:
        org: name of the organization to edit
        description: The description of the organization
        email: The email address of the organization
        full_name: The full display name of the organization
        location: The location of the organization
        repo_admin_change_team_access: Whether repository administrators can change team access
        visibility: possible values are `public`, `limited` or `private`
        website: The website URL of the organization
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if description != "": args['description'] = description
    if email != "": args['email'] = email
    if full_name != "": args['full_name'] = full_name
    if location != "": args['location'] = location
    if repo_admin_change_team_access: args['repo_admin_change_team_access'] = repo_admin_change_team_access
    if visibility is not None: args['visibility'] = visibility
    if website != "": args['website'] = website
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_edit', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_activity_feeds',
    description="List an organization's activity feeds",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_activity_feeds(org: str, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's activity feeds

    Args:
        org: name of the org
        date: the date of the activities to be found
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if date is not None and date != "": args['date'] = date
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_activity_feeds', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='org_list_labels',
    description="List an organization's labels",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_labels(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's labels

    Args:
        org: name of the organization
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_labels', get_user_token(), **args)
    return {'labels': json_to_toon(data)}

@mcp.tool(
    name='org_create_label',
    description='Create a label for an organization',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def org_create_label(org: str, color: str, description: str, name: str, exclusive: bool = False, is_archived: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a label for an organization

    Args:
        org: name of the organization
        color: color field
        description: Description provides additional context about the label's purpose
        exclusive: exclusive field
        is_archived: is_archived field
        name: name field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['color'] = color
    args['description'] = description
    if exclusive: args['exclusive'] = exclusive
    if is_archived: args['is_archived'] = is_archived
    args['name'] = name
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_create_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_delete_label',
    description='Delete a label',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_delete_label(org: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a label

    Args:
        org: name of the organization
        id: id of the label to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_get_label',
    description='Get a single label',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_get_label(org: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a single label

    Args:
        org: name of the organization
        id: id of the label to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_edit_label',
    description='Update a label',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_edit_label(org: str, id: int, color: str = '', description: str = '', exclusive: bool = False, is_archived: bool = False, name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a label

    Args:
        org: name of the organization
        id: id of the label to edit
        color: color field
        description: Description provides additional context about the label's purpose
        exclusive: exclusive field
        is_archived: is_archived field
        name: Name is the new display name for the label
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['id'] = id
    if color != "": args['color'] = color
    if description != "": args['description'] = description
    if exclusive: args['exclusive'] = exclusive
    if is_archived: args['is_archived'] = is_archived
    if name != "": args['name'] = name
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_edit_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_members',
    description="List an organization's members",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_members(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's members

    Args:
        org: name of the organization
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_members', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='org_delete_member',
    description='Remove a member from an organization',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_delete_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a member from an organization

    Args:
        org: name of the organization
        username: username of the user to remove from the organization
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_is_member',
    description='Check if a user is a member of an organization',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_is_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a user is a member of an organization

    Args:
        org: name of the organization
        username: username of the user to check for an organization membership
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_is_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_public_members',
    description="List an organization's public members",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_public_members(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's public members

    Args:
        org: name of the organization
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_public_members', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='org_conceal_member',
    description="Conceal a user's membership",
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_conceal_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Conceal a user's membership

    Args:
        org: name of the organization
        username: username of the user whose membership is to be concealed
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_conceal_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_is_public_member',
    description='Check if a user is a public member of an organization',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_is_public_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a user is a public member of an organization

    Args:
        org: name of the organization
        username: username of the user to check for a public organization membership
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_is_public_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_publicize_member',
    description="Publicize a user's membership",
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_publicize_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Publicize a user's membership

    Args:
        org: name of the organization
        username: username of the user whose membership is to be publicized
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_publicize_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='rename_org',
    description='Rename an organization',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def rename_org(org: str, new_name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Rename an organization

    Args:
        org: existing org name
        new_name: New username for this org. This name cannot be in use yet by any other user.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['new_name'] = new_name
    if sudo: args["sudo"] = sudo
    data = await get_client().call('rename_org', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_repos',
    description="List an organization's repos",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_repos(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's repos

    Args:
        org: name of the organization
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_repos', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='create_org_repo',
    description='Create a repository in an organization',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def create_org_repo(org: str, description: str, name: str, auto_init: bool = False, default_branch: str = '', gitignores: str = '', issue_labels: str = '', license: str = '', object_format_name: Optional[Literal['sha1', 'sha256']] = 'sha1', private: bool = False, readme: str = '', template: bool = False, trust_model: Optional[Literal['default', 'collaborator', 'committer', 'collaboratorcommitter']] = 'default', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository in an organization

    Args:
        org: name of organization
        auto_init: Whether the repository should be auto-initialized?
        default_branch: DefaultBranch of the repository (used when initializes and in template)
        description: Description of the repository to create
        gitignores: Gitignores to use
        issue_labels: Label-Set to use
        license: License to use
        name: Name of the repository to create
        object_format_name: ObjectFormatName of the underlying git repository
        private: Whether the repository is private
        readme: Readme of the repository to create
        template: Whether the repository is template
        trust_model: TrustModel of the repository
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if auto_init: args['auto_init'] = auto_init
    if default_branch != "": args['default_branch'] = default_branch
    args['description'] = description
    if gitignores != "": args['gitignores'] = gitignores
    if issue_labels != "": args['issue_labels'] = issue_labels
    if license != "": args['license'] = license
    args['name'] = name
    if object_format_name is not None: args['object_format_name'] = object_format_name
    if private: args['private'] = private
    if readme != "": args['readme'] = readme
    if template: args['template'] = template
    if trust_model is not None: args['trust_model'] = trust_model
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_org_repo', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_teams',
    description="List an organization's teams",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_teams(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's teams

    Args:
        org: name of the organization
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_teams', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    name='org_create_team',
    description='Create a team',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def org_create_team(org: str, description: str, name: str, permission: Literal['read', 'write', 'admin'], can_create_org_repo: bool = False, includes_all_repositories: bool = False, units: Optional[list[str]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a team

    Args:
        org: name of the organization
        can_create_org_repo: Whether the team can create repositories in the organization
        description: The description of the team
        includes_all_repositories: Whether the team has access to all repositories in the organization
        name: name field
        permission: permission field
        units: units field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if can_create_org_repo: args['can_create_org_repo'] = can_create_org_repo
    args['description'] = description
    if includes_all_repositories: args['includes_all_repositories'] = includes_all_repositories
    args['name'] = name
    args['permission'] = permission
    if units is not None: args['units'] = units
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_create_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='team_search',
    description='Search for teams within an organization',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def team_search(org: str, q: str = "", include_desc: bool = False, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for teams within an organization

    Args:
        org: name of the organization
        q: keywords to search
        include_desc: include search within team description (defaults to true)
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if q is not None and q != "": args['q'] = q
    if include_desc is not None and include_desc != "": args['include_desc'] = include_desc
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('team_search', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='list_packages',
    description='Gets all packages of an owner',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def list_packages(owner: str, page: int = 1, limit: int = 50, type: Literal['alpine', 'cargo', 'chef', 'composer', 'conan', 'conda', 'container', 'cran', 'debian', 'generic', 'go', 'helm', 'maven', 'npm', 'nuget', 'pub', 'pypi', 'rpm', 'rubygems', 'swift', 'vagrant'] = 'alpine', q: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets all packages of an owner

    Args:
        owner: owner of the packages
        page: page number of results to return (1-based)
        limit: page size of results
        type: package type filter
        q: name filter
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if type is not None and type != "": args['type'] = type
    if q is not None and q != "": args['q'] = q
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('list_packages', get_user_token(), **args)
    return {'packages': json_to_toon(data)}

@mcp.tool(
    name='list_package_versions',
    description='Gets all versions of a package',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def list_package_versions(owner: str, type: str, name: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets all versions of a package

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('list_package_versions', get_user_token(), **args)
    return {'packages': json_to_toon(data)}

@mcp.tool(
    name='get_latest_package_version',
    description='Gets the latest version of a package',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def get_latest_package_version(owner: str, type: str, name: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the latest version of a package

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_latest_package_version', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='link_package',
    description='Link a package to a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def link_package(owner: str, type: str, name: str, repo_name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Link a package to a repository

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        repo_name: name of the repository to link.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    args['repo_name'] = repo_name
    if sudo: args["sudo"] = sudo
    data = await get_client().call('link_package', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='unlink_package',
    description='Unlink a package from a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def unlink_package(owner: str, type: str, name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unlink a package from a repository

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    if sudo: args["sudo"] = sudo
    data = await get_client().call('unlink_package', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='delete_package',
    description='Delete a package',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def delete_package(owner: str, type: str, name: str, version: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a package

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        version: version of the package
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    args['version'] = version
    if sudo: args["sudo"] = sudo
    data = await get_client().call('delete_package', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='get_package',
    description='Gets a package',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def get_package(owner: str, type: str, name: str, version: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets a package

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        version: version of the package
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    args['version'] = version
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_package', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='list_package_files',
    description='Gets all files of a package',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def list_package_files(owner: str, type: str, name: str, version: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets all files of a package

    Args:
        owner: owner of the package
        type: type of the package
        name: name of the package
        version: version of the package
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['type'] = type
    args['name'] = name
    args['version'] = version
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('list_package_files', get_user_token(), **args)
    return {'package_files': json_to_toon(data)}

@mcp.tool(
    name='issue_search_issues',
    description='Search for issues across the repositories that the user has access to',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_search_issues(state: Literal['open', 'closed', 'all'] = 'open', labels: str = "", milestones: str = "", q: str = "", priority_repo_id: int = 0, type: Literal['issues', 'pulls'] = 'issues', since: str = "", before: str = "", assigned: bool = False, created: bool = False, mentioned: bool = False, review_requested: bool = False, reviewed: bool = False, owner: str = "", team: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for issues across the repositories that the user has access to

    Args:
        state: State of the issue
        labels: Comma-separated list of label names. Fetch only issues that have any of these labels. Non existent labels are discarded.
        milestones: Comma-separated list of milestone names. Fetch only issues that have any of these milestones. Non existent milestones are discarded.
        q: Search string
        priority_repo_id: Repository ID to prioritize in the results
        type: Filter by issue type
        since: Only show issues updated after the given time (RFC 3339 format) ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show issues updated before the given time (RFC 3339 format) ISO 8601 format (2026-06-22T15:00:00-04:00).
        assigned: Filter issues or pulls assigned to the authenticated user
        created: Filter issues or pulls created by the authenticated user
        mentioned: Filter issues or pulls mentioning the authenticated user
        review_requested: Filter pull requests where the authenticated user's review was requested
        reviewed: Filter pull requests reviewed by the authenticated user
        owner: Filter by repository owner
        team: Filter by team (requires organization owner parameter)
        page: Page number of results to return (1-based)
        limit: Number of items per page
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if state is not None and state != "": args['state'] = state
    if labels is not None and labels != "": args['labels'] = labels
    if milestones is not None and milestones != "": args['milestones'] = milestones
    if q is not None and q != "": args['q'] = q
    if priority_repo_id is not None and priority_repo_id != "": args['priority_repo_id'] = priority_repo_id
    if type is not None and type != "": args['type'] = type
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if assigned is not None and assigned != "": args['assigned'] = assigned
    if created is not None and created != "": args['created'] = created
    if mentioned is not None and mentioned != "": args['mentioned'] = mentioned
    if review_requested is not None and review_requested != "": args['review_requested'] = review_requested
    if reviewed is not None and reviewed != "": args['reviewed'] = reviewed
    if owner is not None and owner != "": args['owner'] = owner
    if team is not None and team != "": args['team'] = team
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_search_issues', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='repo_migrate',
    description='Migrate a remote git repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_migrate(clone_addr: str, description: str, repo_name: str, auth_password: str = '', auth_token: str = '', auth_username: str = '', aws_access_key_id: str = '', aws_secret_access_key: str = '', issues: bool = False, labels: bool = False, lfs: bool = False, lfs_endpoint: str = '', milestones: bool = False, mirror: bool = False, mirror_interval: str = '', private: bool = False, pull_requests: bool = False, releases: bool = False, repo_owner: str = '', service: Optional[Literal['git', 'github', 'gitea', 'gitlab', 'gogs', 'onedev', 'gitbucket', 'codebase', 'codecommit']] = 'git', uid: int = 0, wiki: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Migrate a remote git repository

    Args:
        auth_password: auth_password field
        auth_token: auth_token field
        auth_username: auth_username field
        aws_access_key_id: aws_access_key_id field
        aws_secret_access_key: aws_secret_access_key field
        clone_addr: clone_addr field
        description: description field
        issues: issues field
        labels: labels field
        lfs: lfs field
        lfs_endpoint: lfs_endpoint field
        milestones: milestones field
        mirror: mirror field
        mirror_interval: mirror_interval field
        private: private field
        pull_requests: pull_requests field
        releases: releases field
        repo_name: repo_name field
        repo_owner: the organization's name or individual user's name who will own the migrated repository
        service: service field
        uid: deprecated (only for backwards compatibility, use repo_owner instead)
        wiki: wiki field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if auth_password != "": args['auth_password'] = auth_password
    if auth_token != "": args['auth_token'] = auth_token
    if auth_username != "": args['auth_username'] = auth_username
    if aws_access_key_id != "": args['aws_access_key_id'] = aws_access_key_id
    if aws_secret_access_key != "": args['aws_secret_access_key'] = aws_secret_access_key
    args['clone_addr'] = clone_addr
    args['description'] = description
    if issues: args['issues'] = issues
    if labels: args['labels'] = labels
    if lfs: args['lfs'] = lfs
    if lfs_endpoint != "": args['lfs_endpoint'] = lfs_endpoint
    if milestones: args['milestones'] = milestones
    if mirror: args['mirror'] = mirror
    if mirror_interval != "": args['mirror_interval'] = mirror_interval
    if private: args['private'] = private
    if pull_requests: args['pull_requests'] = pull_requests
    if releases: args['releases'] = releases
    args['repo_name'] = repo_name
    if repo_owner != "": args['repo_owner'] = repo_owner
    if service is not None: args['service'] = service
    if uid != 0: args['uid'] = uid
    if wiki: args['wiki'] = wiki
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_migrate', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_search',
    description='Search for repositories',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_search(q: str = "", topic: bool = False, includeDesc: bool = False, uid: int = 0, priority_owner_id: int = 0, team_id: int = 0, starredBy: int = 0, private: bool = False, is_private: bool = False, template: bool = False, archived: bool = False, mode: str = "", exclusive: bool = False, sort: str = "", order: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for repositories

    Args:
        q: keyword
        topic: Limit search to repositories with keyword as topic
        includeDesc: include search of keyword within repository description
        uid: search only for repos that the user with the given id owns or contributes to
        priority_owner_id: repo owner to prioritize in the results
        team_id: search only for repos that belong to the given team id
        starredBy: search only for repos that the user with the given id has starred
        private: include private repositories this user has access to (defaults to true)
        is_private: show only pubic, private or all repositories (defaults to all)
        template: include template repositories this user has access to (defaults to true)
        archived: show only archived, non-archived or all repositories (defaults to all)
        mode: type of repository to search for. Supported values are "fork", "source", "mirror" and "collaborative"
        exclusive: if `uid` is given, search only for repos that the user owns
        sort: sort repos by attribute. Supported values are "alpha", "created", "updated", "size", "git_size", "lfs_size", "stars", "forks" and "id". Default is "alpha"
        order: sort order, either "asc" (ascending) or "desc" (descending). Default is "asc", ignored if "sort" is not specified.
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if q is not None and q != "": args['q'] = q
    if topic is not None and topic != "": args['topic'] = topic
    if includeDesc is not None and includeDesc != "": args['includeDesc'] = includeDesc
    if uid is not None and uid != "": args['uid'] = uid
    if priority_owner_id is not None and priority_owner_id != "": args['priority_owner_id'] = priority_owner_id
    if team_id is not None and team_id != "": args['team_id'] = team_id
    if starredBy is not None and starredBy != "": args['starredBy'] = starredBy
    if private is not None and private != "": args['private'] = private
    if is_private is not None and is_private != "": args['is_private'] = is_private
    if template is not None and template != "": args['template'] = template
    if archived is not None and archived != "": args['archived'] = archived
    if mode is not None and mode != "": args['mode'] = mode
    if exclusive is not None and exclusive != "": args['exclusive'] = exclusive
    if sort is not None and sort != "": args['sort'] = sort
    if order is not None and order != "": args['order'] = order
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_search', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='repo_delete',
    description='Delete a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete(owner: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a repository

    Args:
        owner: owner of the repo to delete
        repo: name of the repo to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get',
    description='Get a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_edit',
    description="Edit a repository's properties. Only fields that are set will be changed.",
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_edit(owner: str, repo: str, allow_fast_forward_only_merge: bool = False, allow_manual_merge: bool = False, allow_merge_commits: bool = False, allow_rebase: bool = False, allow_rebase_explicit: bool = False, allow_rebase_update: bool = False, allow_squash_merge: bool = False, archived: bool = False, autodetect_manual_merge: bool = False, default_allow_maintainer_edit: bool = False, default_branch: str = '', default_delete_branch_after_merge: bool = False, default_merge_style: str = '', description: str = '', enable_prune: bool = False, external_tracker: ExternalTracker = None, external_wiki: ExternalWiki = None, has_actions: bool = False, has_code: bool = False, has_issues: bool = False, has_packages: bool = False, has_projects: bool = False, has_pull_requests: bool = False, has_releases: bool = False, has_wiki: bool = False, ignore_whitespace_conflicts: bool = False, internal_tracker: InternalTracker = None, mirror_interval: str = '', name: str = '', private: bool = False, projects_mode: str = '', template: bool = False, website: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a repository's properties. Only fields that are set will be changed.

    Args:
        owner: owner of the repo to edit
        repo: name of the repo to edit
        allow_fast_forward_only_merge: either `true` to allow fast-forward-only merging pull requests, or `false` to prevent fast-forward-only merging.
        allow_manual_merge: either `true` to allow mark pr as merged manually, or `false` to prevent it.
        allow_merge_commits: either `true` to allow merging pull requests with a merge commit, or `false` to prevent merging pull requests with merge commits.
        allow_rebase: either `true` to allow rebase-merging pull requests, or `false` to prevent rebase-merging.
        allow_rebase_explicit: either `true` to allow rebase with explicit merge commits (--no-ff), or `false` to prevent rebase with explicit merge commits.
        allow_rebase_update: either `true` to allow updating pull request branch by rebase, or `false` to prevent it.
        allow_squash_merge: either `true` to allow squash-merging pull requests, or `false` to prevent squash-merging.
        archived: set to `true` to archive this repository.
        autodetect_manual_merge: either `true` to enable AutodetectManualMerge, or `false` to prevent it. Note: In some special cases, misjudgments can occur.
        default_allow_maintainer_edit: set to `true` to allow edits from maintainers by default
        default_branch: sets the default branch for this repository.
        default_delete_branch_after_merge: set to `true` to delete pr branch after merge by default
        default_merge_style: set to a merge style to be used by this repository: "merge", "rebase", "rebase-merge", "squash", or "fast-forward-only".
        description: a short description of the repository.
        enable_prune: enable prune - remove obsolete remote-tracking references when mirroring
        external_tracker: external_tracker field
        external_wiki: external_wiki field
        has_actions: either `true` to enable actions unit, or `false` to disable them.
        has_code: either `true` to enable code for this repository or `false` to disable it.
        has_issues: either `true` to enable issues for this repository or `false` to disable them.
        has_packages: either `true` to enable packages unit, or `false` to disable them.
        has_projects: either `true` to enable project unit, or `false` to disable them.
        has_pull_requests: either `true` to allow pull requests, or `false` to prevent pull request.
        has_releases: either `true` to enable releases unit, or `false` to disable them.
        has_wiki: either `true` to enable the wiki for this repository or `false` to disable it.
        ignore_whitespace_conflicts: either `true` to ignore whitespace for conflicts, or `false` to not ignore whitespace.
        internal_tracker: internal_tracker field
        mirror_interval: set to a string like `8h30m0s` to set the mirror interval time
        name: name of the repository
        private: either `true` to make the repository private or `false` to make it public. Note: you will get a 422 error if the organization restricts changing repository visibility to organization owners and a non-owner tries to change the value of private.
        projects_mode: `repo` to only allow repo-level projects, `owner` to only allow owner projects, `all` to allow both.
        template: either `true` to make this repository a template or `false` to make it a normal repository
        website: a URL with more information about the repository.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if allow_fast_forward_only_merge: args['allow_fast_forward_only_merge'] = allow_fast_forward_only_merge
    if allow_manual_merge: args['allow_manual_merge'] = allow_manual_merge
    if allow_merge_commits: args['allow_merge_commits'] = allow_merge_commits
    if allow_rebase: args['allow_rebase'] = allow_rebase
    if allow_rebase_explicit: args['allow_rebase_explicit'] = allow_rebase_explicit
    if allow_rebase_update: args['allow_rebase_update'] = allow_rebase_update
    if allow_squash_merge: args['allow_squash_merge'] = allow_squash_merge
    if archived: args['archived'] = archived
    if autodetect_manual_merge: args['autodetect_manual_merge'] = autodetect_manual_merge
    if default_allow_maintainer_edit: args['default_allow_maintainer_edit'] = default_allow_maintainer_edit
    if default_branch != "": args['default_branch'] = default_branch
    if default_delete_branch_after_merge: args['default_delete_branch_after_merge'] = default_delete_branch_after_merge
    if default_merge_style != "": args['default_merge_style'] = default_merge_style
    if description != "": args['description'] = description
    if enable_prune: args['enable_prune'] = enable_prune
    if external_tracker is not None: args['external_tracker'] = external_tracker
    if external_wiki is not None: args['external_wiki'] = external_wiki
    if has_actions: args['has_actions'] = has_actions
    if has_code: args['has_code'] = has_code
    if has_issues: args['has_issues'] = has_issues
    if has_packages: args['has_packages'] = has_packages
    if has_projects: args['has_projects'] = has_projects
    if has_pull_requests: args['has_pull_requests'] = has_pull_requests
    if has_releases: args['has_releases'] = has_releases
    if has_wiki: args['has_wiki'] = has_wiki
    if ignore_whitespace_conflicts: args['ignore_whitespace_conflicts'] = ignore_whitespace_conflicts
    if internal_tracker is not None: args['internal_tracker'] = internal_tracker
    if mirror_interval != "": args['mirror_interval'] = mirror_interval
    if name != "": args['name'] = name
    if private: args['private'] = private
    if projects_mode != "": args['projects_mode'] = projects_mode
    if template: args['template'] = template
    if website != "": args['website'] = website
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_activity_feeds',
    description="List a repository's activity feeds",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_activity_feeds(owner: str, repo: str, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's activity feeds

    Args:
        owner: owner of the repo
        repo: name of the repo
        date: the date of the activities to be found
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if date is not None and date != "": args['date'] = date
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_activity_feeds', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='repo_get_assignees',
    description='Return all users that have write access and can be assigned to issues',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_assignees(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Return all users that have write access and can be assigned to issues

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_assignees', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='repo_list_branch_protection',
    description='List branch protections for a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_branch_protection(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List branch protections for a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_branch_protection', get_user_token(), **args)
    return {'branch_protections': json_to_toon(data)}

@mcp.tool(
    name='repo_create_branch_protection',
    description='Create a branch protections for a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_branch_protection(owner: str, repo: str, branch_name: str, approvals_whitelist_teams: Optional[list[str]] = None, approvals_whitelist_username: Optional[list[str]] = None, block_admin_merge_override: bool = False, block_on_official_review_requests: bool = False, block_on_outdated_branch: bool = False, block_on_rejected_reviews: bool = False, dismiss_stale_approvals: bool = False, enable_approvals_whitelist: bool = False, enable_force_push: bool = False, enable_force_push_allowlist: bool = False, enable_merge_whitelist: bool = False, enable_push: bool = False, enable_push_whitelist: bool = False, enable_status_check: bool = False, force_push_allowlist_deploy_keys: bool = False, force_push_allowlist_teams: Optional[list[str]] = None, force_push_allowlist_usernames: Optional[list[str]] = None, ignore_stale_approvals: bool = False, merge_whitelist_teams: Optional[list[str]] = None, merge_whitelist_usernames: Optional[list[str]] = None, priority: int = 0, protected_file_patterns: str = '', push_whitelist_deploy_keys: bool = False, push_whitelist_teams: Optional[list[str]] = None, push_whitelist_usernames: Optional[list[str]] = None, require_signed_commits: bool = False, required_approvals: int = 0, rule_name: str = '', status_check_contexts: Optional[list[str]] = None, unprotected_file_patterns: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a branch protections for a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        approvals_whitelist_teams: approvals_whitelist_teams field
        approvals_whitelist_username: approvals_whitelist_username field
        block_admin_merge_override: block_admin_merge_override field
        block_on_official_review_requests: block_on_official_review_requests field
        block_on_outdated_branch: block_on_outdated_branch field
        block_on_rejected_reviews: block_on_rejected_reviews field
        branch_name: Deprecated: true
        dismiss_stale_approvals: dismiss_stale_approvals field
        enable_approvals_whitelist: enable_approvals_whitelist field
        enable_force_push: enable_force_push field
        enable_force_push_allowlist: enable_force_push_allowlist field
        enable_merge_whitelist: enable_merge_whitelist field
        enable_push: enable_push field
        enable_push_whitelist: enable_push_whitelist field
        enable_status_check: enable_status_check field
        force_push_allowlist_deploy_keys: force_push_allowlist_deploy_keys field
        force_push_allowlist_teams: force_push_allowlist_teams field
        force_push_allowlist_usernames: force_push_allowlist_usernames field
        ignore_stale_approvals: ignore_stale_approvals field
        merge_whitelist_teams: merge_whitelist_teams field
        merge_whitelist_usernames: merge_whitelist_usernames field
        priority: priority field
        protected_file_patterns: protected_file_patterns field
        push_whitelist_deploy_keys: push_whitelist_deploy_keys field
        push_whitelist_teams: push_whitelist_teams field
        push_whitelist_usernames: push_whitelist_usernames field
        require_signed_commits: require_signed_commits field
        required_approvals: required_approvals field
        rule_name: rule_name field
        status_check_contexts: status_check_contexts field
        unprotected_file_patterns: unprotected_file_patterns field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if approvals_whitelist_teams is not None: args['approvals_whitelist_teams'] = approvals_whitelist_teams
    if approvals_whitelist_username is not None: args['approvals_whitelist_username'] = approvals_whitelist_username
    if block_admin_merge_override: args['block_admin_merge_override'] = block_admin_merge_override
    if block_on_official_review_requests: args['block_on_official_review_requests'] = block_on_official_review_requests
    if block_on_outdated_branch: args['block_on_outdated_branch'] = block_on_outdated_branch
    if block_on_rejected_reviews: args['block_on_rejected_reviews'] = block_on_rejected_reviews
    args['branch_name'] = branch_name
    if dismiss_stale_approvals: args['dismiss_stale_approvals'] = dismiss_stale_approvals
    if enable_approvals_whitelist: args['enable_approvals_whitelist'] = enable_approvals_whitelist
    if enable_force_push: args['enable_force_push'] = enable_force_push
    if enable_force_push_allowlist: args['enable_force_push_allowlist'] = enable_force_push_allowlist
    if enable_merge_whitelist: args['enable_merge_whitelist'] = enable_merge_whitelist
    if enable_push: args['enable_push'] = enable_push
    if enable_push_whitelist: args['enable_push_whitelist'] = enable_push_whitelist
    if enable_status_check: args['enable_status_check'] = enable_status_check
    if force_push_allowlist_deploy_keys: args['force_push_allowlist_deploy_keys'] = force_push_allowlist_deploy_keys
    if force_push_allowlist_teams is not None: args['force_push_allowlist_teams'] = force_push_allowlist_teams
    if force_push_allowlist_usernames is not None: args['force_push_allowlist_usernames'] = force_push_allowlist_usernames
    if ignore_stale_approvals: args['ignore_stale_approvals'] = ignore_stale_approvals
    if merge_whitelist_teams is not None: args['merge_whitelist_teams'] = merge_whitelist_teams
    if merge_whitelist_usernames is not None: args['merge_whitelist_usernames'] = merge_whitelist_usernames
    if priority != 0: args['priority'] = priority
    if protected_file_patterns != "": args['protected_file_patterns'] = protected_file_patterns
    if push_whitelist_deploy_keys: args['push_whitelist_deploy_keys'] = push_whitelist_deploy_keys
    if push_whitelist_teams is not None: args['push_whitelist_teams'] = push_whitelist_teams
    if push_whitelist_usernames is not None: args['push_whitelist_usernames'] = push_whitelist_usernames
    if require_signed_commits: args['require_signed_commits'] = require_signed_commits
    if required_approvals != 0: args['required_approvals'] = required_approvals
    if rule_name != "": args['rule_name'] = rule_name
    if status_check_contexts is not None: args['status_check_contexts'] = status_check_contexts
    if unprotected_file_patterns != "": args['unprotected_file_patterns'] = unprotected_file_patterns
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_branch_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_update_branch_protection_priories',
    description='Update the priorities of branch protections for a repository.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_update_branch_protection_priories(owner: str, repo: str, ids: Optional[list[int]] = None, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update the priorities of branch protections for a repository.

    Args:
        owner: owner of the repo
        repo: name of the repo
        ids: ids field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if ids is not None: args['ids'] = ids
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_update_branch_protection_priories', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_branch_protection',
    description='Delete a specific branch protection for the repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_branch_protection(owner: str, repo: str, name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific branch protection for the repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        name: name of protected branch
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['name'] = name
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_branch_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_branch_protection',
    description='Get a specific branch protection for the repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_branch_protection(owner: str, repo: str, name: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific branch protection for the repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        name: name of protected branch
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['name'] = name
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_branch_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_edit_branch_protection',
    description='Edit a branch protections for a repository. Only fields that are set will be changed',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_edit_branch_protection(owner: str, repo: str, name: str, approvals_whitelist_teams: Optional[list[str]] = None, approvals_whitelist_username: Optional[list[str]] = None, block_admin_merge_override: bool = False, block_on_official_review_requests: bool = False, block_on_outdated_branch: bool = False, block_on_rejected_reviews: bool = False, dismiss_stale_approvals: bool = False, enable_approvals_whitelist: bool = False, enable_force_push: bool = False, enable_force_push_allowlist: bool = False, enable_merge_whitelist: bool = False, enable_push: bool = False, enable_push_whitelist: bool = False, enable_status_check: bool = False, force_push_allowlist_deploy_keys: bool = False, force_push_allowlist_teams: Optional[list[str]] = None, force_push_allowlist_usernames: Optional[list[str]] = None, ignore_stale_approvals: bool = False, merge_whitelist_teams: Optional[list[str]] = None, merge_whitelist_usernames: Optional[list[str]] = None, priority: int = 0, protected_file_patterns: str = '', push_whitelist_deploy_keys: bool = False, push_whitelist_teams: Optional[list[str]] = None, push_whitelist_usernames: Optional[list[str]] = None, require_signed_commits: bool = False, required_approvals: int = 0, status_check_contexts: Optional[list[str]] = None, unprotected_file_patterns: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a branch protections for a repository. Only fields that are set will be changed

    Args:
        owner: owner of the repo
        repo: name of the repo
        name: name of protected branch
        approvals_whitelist_teams: approvals_whitelist_teams field
        approvals_whitelist_username: approvals_whitelist_username field
        block_admin_merge_override: block_admin_merge_override field
        block_on_official_review_requests: block_on_official_review_requests field
        block_on_outdated_branch: block_on_outdated_branch field
        block_on_rejected_reviews: block_on_rejected_reviews field
        dismiss_stale_approvals: dismiss_stale_approvals field
        enable_approvals_whitelist: enable_approvals_whitelist field
        enable_force_push: enable_force_push field
        enable_force_push_allowlist: enable_force_push_allowlist field
        enable_merge_whitelist: enable_merge_whitelist field
        enable_push: enable_push field
        enable_push_whitelist: enable_push_whitelist field
        enable_status_check: enable_status_check field
        force_push_allowlist_deploy_keys: force_push_allowlist_deploy_keys field
        force_push_allowlist_teams: force_push_allowlist_teams field
        force_push_allowlist_usernames: force_push_allowlist_usernames field
        ignore_stale_approvals: ignore_stale_approvals field
        merge_whitelist_teams: merge_whitelist_teams field
        merge_whitelist_usernames: merge_whitelist_usernames field
        priority: priority field
        protected_file_patterns: protected_file_patterns field
        push_whitelist_deploy_keys: push_whitelist_deploy_keys field
        push_whitelist_teams: push_whitelist_teams field
        push_whitelist_usernames: push_whitelist_usernames field
        require_signed_commits: require_signed_commits field
        required_approvals: required_approvals field
        status_check_contexts: status_check_contexts field
        unprotected_file_patterns: unprotected_file_patterns field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['name'] = name
    if approvals_whitelist_teams is not None: args['approvals_whitelist_teams'] = approvals_whitelist_teams
    if approvals_whitelist_username is not None: args['approvals_whitelist_username'] = approvals_whitelist_username
    if block_admin_merge_override: args['block_admin_merge_override'] = block_admin_merge_override
    if block_on_official_review_requests: args['block_on_official_review_requests'] = block_on_official_review_requests
    if block_on_outdated_branch: args['block_on_outdated_branch'] = block_on_outdated_branch
    if block_on_rejected_reviews: args['block_on_rejected_reviews'] = block_on_rejected_reviews
    if dismiss_stale_approvals: args['dismiss_stale_approvals'] = dismiss_stale_approvals
    if enable_approvals_whitelist: args['enable_approvals_whitelist'] = enable_approvals_whitelist
    if enable_force_push: args['enable_force_push'] = enable_force_push
    if enable_force_push_allowlist: args['enable_force_push_allowlist'] = enable_force_push_allowlist
    if enable_merge_whitelist: args['enable_merge_whitelist'] = enable_merge_whitelist
    if enable_push: args['enable_push'] = enable_push
    if enable_push_whitelist: args['enable_push_whitelist'] = enable_push_whitelist
    if enable_status_check: args['enable_status_check'] = enable_status_check
    if force_push_allowlist_deploy_keys: args['force_push_allowlist_deploy_keys'] = force_push_allowlist_deploy_keys
    if force_push_allowlist_teams is not None: args['force_push_allowlist_teams'] = force_push_allowlist_teams
    if force_push_allowlist_usernames is not None: args['force_push_allowlist_usernames'] = force_push_allowlist_usernames
    if ignore_stale_approvals: args['ignore_stale_approvals'] = ignore_stale_approvals
    if merge_whitelist_teams is not None: args['merge_whitelist_teams'] = merge_whitelist_teams
    if merge_whitelist_usernames is not None: args['merge_whitelist_usernames'] = merge_whitelist_usernames
    if priority != 0: args['priority'] = priority
    if protected_file_patterns != "": args['protected_file_patterns'] = protected_file_patterns
    if push_whitelist_deploy_keys: args['push_whitelist_deploy_keys'] = push_whitelist_deploy_keys
    if push_whitelist_teams is not None: args['push_whitelist_teams'] = push_whitelist_teams
    if push_whitelist_usernames is not None: args['push_whitelist_usernames'] = push_whitelist_usernames
    if require_signed_commits: args['require_signed_commits'] = require_signed_commits
    if required_approvals != 0: args['required_approvals'] = required_approvals
    if status_check_contexts is not None: args['status_check_contexts'] = status_check_contexts
    if unprotected_file_patterns != "": args['unprotected_file_patterns'] = unprotected_file_patterns
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_branch_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_branches',
    description="List a repository's branches",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_branches(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's branches

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_branches', get_user_token(), **args)
    return {'branches': json_to_toon(data)}

@mcp.tool(
    name='repo_create_branch',
    description='Create a branch',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_branch(owner: str, repo: str, new_branch_name: str, old_branch_name: str = '', old_ref_name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a branch

    Args:
        owner: owner of the repo
        repo: name of the repo
        new_branch_name: Name of the branch to create
        old_branch_name: Deprecated: true Name of the old branch to create from
        old_ref_name: Name of the old branch/tag/commit to create from
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['new_branch_name'] = new_branch_name
    if old_branch_name != "": args['old_branch_name'] = old_branch_name
    if old_ref_name != "": args['old_ref_name'] = old_ref_name
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_branch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_branch',
    description='Delete a specific branch from a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_branch(owner: str, repo: str, branch: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific branch from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        branch: branch to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['branch'] = branch
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_branch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_branch',
    description='Retrieve a specific branch from a repository, including its effective branch protection',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_branch(owner: str, repo: str, branch: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Retrieve a specific branch from a repository, including its effective branch protection

    Args:
        owner: owner of the repo
        repo: name of the repo
        branch: branch to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['branch'] = branch
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_branch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_rename_branch',
    description='Rename a branch',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_rename_branch(owner: str, repo: str, branch: str, name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Rename a branch

    Args:
        owner: owner of the repo
        repo: name of the repo
        branch: name of the branch
        name: New branch name
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['branch'] = branch
    args['name'] = name
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_rename_branch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_collaborators',
    description="List a repository's collaborators",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_collaborators(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's collaborators

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_collaborators', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='repo_delete_collaborator',
    description='Delete a collaborator from a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_collaborator(owner: str, repo: str, collaborator: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a collaborator from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        collaborator: username of the collaborator to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['collaborator'] = collaborator
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_collaborator', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_check_collaborator',
    description='Check if a user is a collaborator of a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_check_collaborator(owner: str, repo: str, collaborator: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a user is a collaborator of a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        collaborator: username of the user to check for being a collaborator
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['collaborator'] = collaborator
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_check_collaborator', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_add_collaborator',
    description='Add or Update a collaborator to a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_add_collaborator(owner: str, repo: str, collaborator: str, permission: Optional[Literal['read', 'write', 'admin']] = 'read', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add or Update a collaborator to a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        collaborator: username of the user to add or update as a collaborator
        permission: permission field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['collaborator'] = collaborator
    if permission is not None: args['permission'] = permission
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_add_collaborator', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_repo_permissions',
    description='Get repository permissions for a user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_repo_permissions(owner: str, repo: str, collaborator: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get repository permissions for a user

    Args:
        owner: owner of the repo
        repo: name of the repo
        collaborator: username of the collaborator whose permissions are to be obtained
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['collaborator'] = collaborator
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_repo_permissions', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_all_commits',
    description='Get a list of all commits from a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_all_commits(owner: str, repo: str, sha: str = "", path: str = "", since: str = "", until: str = "", stat: bool = False, verification: bool = False, files: bool = False, page: int = 1, limit: int = 50, query_not: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a list of all commits from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: SHA or branch to start listing commits from (usually 'master')
        path: filepath of a file/dir
        since: Only commits after this date will be returned (ISO 8601 format) ISO 8601 format (2026-06-22T15:00:00-04:00).
        until: Only commits before this date will be returned (ISO 8601 format) ISO 8601 format (2026-06-22T15:00:00-04:00).
        stat: include diff stats for every commit (disable for speedup, default 'true')
        verification: include verification for every commit (disable for speedup, default 'true')
        files: include a list of affected files for every commit (disable for speedup, default 'true')
        page: page number of results to return (1-based)
        limit: page size of results (ignored if used with 'path')
        query_not: commits that match the given specifier will not be listed.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if sha is not None and sha != "": args['sha'] = sha
    if path is not None and path != "": args['path'] = path
    if since is not None and since != "": args['since'] = since
    if until is not None and until != "": args['until'] = until
    if stat is not None and stat != "": args['stat'] = stat
    if verification is not None and verification != "": args['verification'] = verification
    if files is not None and files != "": args['files'] = files
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if query_not is not None and query_not != "": args['not'] = query_not
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_all_commits', get_user_token(), **args)
    return {'commits': json_to_toon(data)}

@mcp.tool(
    name='repo_get_combined_status_by_ref',
    description="Get a commit's combined status, by branch/tag/commit reference",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_combined_status_by_ref(owner: str, repo: str, ref: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a commit's combined status, by branch/tag/commit reference

    Args:
        owner: owner of the repo
        repo: name of the repo
        ref: name of branch/tag/commit
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['ref'] = ref
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_combined_status_by_ref', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_statuses_by_ref',
    description="Get a commit's statuses, by branch/tag/commit reference",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_statuses_by_ref(owner: str, repo: str, ref: str, sort: Literal['oldest', 'recentupdate', 'leastupdate', 'leastindex', 'highestindex'] = 'oldest', state: Literal['pending', 'success', 'error', 'failure', 'warning'] = 'pending', page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a commit's statuses, by branch/tag/commit reference

    Args:
        owner: owner of the repo
        repo: name of the repo
        ref: name of branch/tag/commit
        sort: type of sort
        state: type of state
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['ref'] = ref
    if sort is not None and sort != "": args['sort'] = sort
    if state is not None and state != "": args['state'] = state
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_statuses_by_ref', get_user_token(), **args)
    return {'commit_statuses': json_to_toon(data)}

@mcp.tool(
    name='repo_get_commit_pull_request',
    description='Get the merged pull request of the commit',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_commit_pull_request(owner: str, repo: str, sha: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get the merged pull request of the commit

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: SHA of the commit to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_commit_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_compare_diff',
    description='Get commit comparison information',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_compare_diff(owner: str, repo: str, basehead: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get commit comparison information

    Args:
        owner: owner of the repo
        repo: name of the repo
        basehead: compare two branches or commits
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['basehead'] = basehead
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_compare_diff', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_contents_list',
    description='Gets the metadata of all the entries of the root dir.',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_contents_list(owner: str, repo: str, ref: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the metadata of all the entries of the root dir.

    Args:
        owner: owner of the repo
        repo: name of the repo
        ref: The name of the commit/branch/tag. Default to the repository’s default branch.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if ref is not None and ref != "": args['ref'] = ref
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_contents_list', get_user_token(), **args)
    return {'contents': json_to_toon(data)}

@mcp.tool(
    name='repo_change_files',
    description='Modify multiple files in a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_change_files(owner: str, repo: str, files: list[ChangeFileOperation], author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, message: str = '', new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Modify multiple files in a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        author: author field
        branch: branch (optional) to base this file from. if not given, the default branch is used
        committer: committer field
        dates: dates field
        files: list of file operations
        message: message (optional) for the commit of this file. if not supplied, a default message will be used
        new_branch: new_branch (optional) will make a new branch from `branch` before creating the file
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    if dates is not None: args['dates'] = dates
    args['files'] = files
    if message != "": args['message'] = message
    if new_branch != "": args['new_branch'] = new_branch
    if signoff: args['signoff'] = signoff
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_change_files', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_file',
    description='Delete a file in a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_file(owner: str, repo: str, filepath: str, message: str, sha: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, new_branch: str = '', signoff: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a file in a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        filepath: path of the file to delete
        author: author field
        branch: branch (optional) to base this file from. if not given, the default branch is used
        committer: committer field
        dates: dates field
        message: message (optional) for the commit of this file. if not supplied, a default message will be used
        new_branch: new_branch (optional) will make a new branch from `branch` before creating the file
        sha: the blob ID (SHA) for the file that already exists, it is required for changing existing files
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['filepath'] = filepath
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    if dates is not None: args['dates'] = dates
    args['message'] = message
    if new_branch != "": args['new_branch'] = new_branch
    args['sha'] = sha
    if signoff: args['signoff'] = signoff
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_file', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_contents',
    description='Gets the metadata and contents (if a file) of an entry in a repository, or a list of entries if a dir.',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_contents(owner: str, repo: str, filepath: str, ref: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the metadata and contents (if a file) of an entry in a repository, or a list of entries if a dir.

    Args:
        owner: owner of the repo
        repo: name of the repo
        filepath: path of the dir, file, symlink or submodule in the repo
        ref: The name of the commit/branch/tag. Default to the repository’s default branch.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['filepath'] = filepath
    if ref is not None and ref != "": args['ref'] = ref
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_contents', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_create_file',
    description='Create a file in a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_file(owner: str, repo: str, filepath: str, content: str, message: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a file in a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        filepath: path of the file to create
        author: author field
        branch: branch (optional) to base this file from. if not given, the default branch is used
        committer: committer field
        content: content must be base64 encoded
        dates: dates field
        message: message (optional) for the commit of this file. if not supplied, a default message will be used
        new_branch: new_branch (optional) will make a new branch from `branch` before creating the file
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['filepath'] = filepath
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    args['content'] = content
    if dates is not None: args['dates'] = dates
    args['message'] = message
    if new_branch != "": args['new_branch'] = new_branch
    if signoff: args['signoff'] = signoff
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_file', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_update_file',
    description='Update a file in a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_update_file(owner: str, repo: str, filepath: str, content: str, message: str, sha: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, from_path: str = '', new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a file in a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        filepath: path of the file to update
        author: author field
        branch: branch (optional) to base this file from. if not given, the default branch is used
        committer: committer field
        content: content must be base64 encoded
        dates: dates field
        from_path: from_path (optional) is the path of the original file which will be moved/renamed to the path in the URL
        message: message (optional) for the commit of this file. if not supplied, a default message will be used
        new_branch: new_branch (optional) will make a new branch from `branch` before creating the file
        sha: the blob ID (SHA) for the file that already exists, it is required for changing existing files
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['filepath'] = filepath
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    args['content'] = content
    if dates is not None: args['dates'] = dates
    if from_path != "": args['from_path'] = from_path
    args['message'] = message
    if new_branch != "": args['new_branch'] = new_branch
    args['sha'] = sha
    if signoff: args['signoff'] = signoff
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_update_file', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_apply_diff_patch',
    description='Apply diff patch to repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_apply_diff_patch(owner: str, repo: str, content: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, message: str = '', new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Apply diff patch to repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        author: author field
        branch: branch (optional) to base this file from. if not given, the default branch is used
        committer: committer field
        content: content field
        dates: dates field
        message: message (optional) for the commit of this file. if not supplied, a default message will be used
        new_branch: new_branch (optional) will make a new branch from `branch` before creating the file
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    args['content'] = content
    if dates is not None: args['dates'] = dates
    if message != "": args['message'] = message
    if new_branch != "": args['new_branch'] = new_branch
    if signoff: args['signoff'] = signoff
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_apply_diff_patch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='list_forks',
    description="List a repository's forks",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def list_forks(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's forks

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('list_forks', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='create_fork',
    description='Fork a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def create_fork(owner: str, repo: str, name: str = '', organization: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Fork a repository

    Args:
        owner: owner of the repo to fork
        repo: name of the repo to fork
        name: name of the forked repository
        organization: organization name, if forking into an organization
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if name != "": args['name'] = name
    if organization != "": args['organization'] = organization
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_fork', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='get_blob',
    description='Gets the blob of a repository.',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def get_blob(owner: str, repo: str, sha: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the blob of a repository.

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: sha of the commit
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_blob', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_single_commit',
    description='Get a single commit from a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_single_commit(owner: str, repo: str, sha: str, stat: bool = False, verification: bool = False, files: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a single commit from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: a git ref or commit sha
        stat: include diff stats for every commit (disable for speedup, default 'true')
        verification: include verification for every commit (disable for speedup, default 'true')
        files: include a list of affected files for every commit (disable for speedup, default 'true')
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    if stat is not None and stat != "": args['stat'] = stat
    if verification is not None and verification != "": args['verification'] = verification
    if files is not None and files != "": args['files'] = files
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_single_commit', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_all_git_refs',
    description="Get specified ref or filtered repository's refs",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_all_git_refs(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get specified ref or filtered repository's refs

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_all_git_refs', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='repo_list_git_refs',
    description="Get specified ref or filtered repository's refs",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_git_refs(owner: str, repo: str, ref: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get specified ref or filtered repository's refs

    Args:
        owner: owner of the repo
        repo: name of the repo
        ref: part or full name of the ref
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['ref'] = ref
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_git_refs', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='get_annotated_tag',
    description='Gets the tag object of an annotated tag (not lightweight tags)',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def get_annotated_tag(owner: str, repo: str, sha: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the tag object of an annotated tag (not lightweight tags)

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: sha of the tag. The Git tags API only supports annotated tag objects, not lightweight tags.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_annotated_tag', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='get_tree',
    description='Gets the tree of a repository.',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def get_tree(owner: str, repo: str, sha: str, recursive: bool = False, page: int = 1, per_page: int = 0, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the tree of a repository.

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: sha of the commit
        recursive: show all directories and files
        page: page number; the 'truncated' field in the response will be true if there are still more items after this page, false if the last page
        per_page: number of items per page
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    if recursive is not None and recursive != "": args['recursive'] = recursive
    if page is not None and page != "": args['page'] = page
    if per_page is not None and per_page != "": args['per_page'] = per_page
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_tree', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_issue_templates',
    description='Get available issue templates for a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_issue_templates(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get available issue templates for a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_issue_templates', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='issue_list_issues',
    description="List a repository's issues",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_list_issues(owner: str, repo: str, state: Literal['closed', 'open', 'all'] = 'closed', labels: str = "", q: str = "", type: Literal['issues', 'pulls'] = 'issues', milestones: str = "", since: str = "", before: str = "", created_by: str = "", assigned_by: str = "", mentioned_by: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's issues

    Args:
        owner: owner of the repo
        repo: name of the repo
        state: whether issue is open or closed
        labels: comma separated list of labels. Fetch only issues that have any of this labels. Non existent labels are discarded
        q: search string
        type: filter by type (issues / pulls) if set
        milestones: comma separated list of milestone names or ids. It uses names and fall back to ids. Fetch only issues that have any of this milestones. Non existent milestones are discarded
        since: Only show items updated after the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show items updated before the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        created_by: Only show items which were created by the given user
        assigned_by: Only show items for which the given user is assigned
        mentioned_by: Only show items in which the given user was mentioned
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if state is not None and state != "": args['state'] = state
    if labels is not None and labels != "": args['labels'] = labels
    if q is not None and q != "": args['q'] = q
    if type is not None and type != "": args['type'] = type
    if milestones is not None and milestones != "": args['milestones'] = milestones
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if created_by is not None and created_by != "": args['created_by'] = created_by
    if assigned_by is not None and assigned_by != "": args['assigned_by'] = assigned_by
    if mentioned_by is not None and mentioned_by != "": args['mentioned_by'] = mentioned_by
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_list_issues', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_create_issue',
    description='Create an issue. If using deadline only the date will be taken into account, and time of day ignored.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_create_issue(owner: str, repo: str, body: str, title: str, assignee: str = '', assignees: Optional[list[str]] = None, closed: bool = False, due_date: str = '', labels: Optional[list[int]] = None, milestone: int = 0, ref: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create an issue. If using deadline only the date will be taken into account, and time of day ignored.

    Args:
        owner: owner of the repo
        repo: name of the repo
        assignee: deprecated
        assignees: assignees field
        body: body field
        closed: closed field
        due_date: due_date field ISO 8601 format (2026-06-22T15:00:00-04:00).
        labels: list of label ids
        milestone: milestone id
        ref: ref field
        title: title field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if assignee != "": args['assignee'] = assignee
    if assignees is not None: args['assignees'] = assignees
    args['body'] = body
    if closed: args['closed'] = closed
    if due_date != "": args['due_date'] = due_date
    if labels is not None: args['labels'] = labels
    if milestone != 0: args['milestone'] = milestone
    if ref != "": args['ref'] = ref
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_repo_comments',
    description='List all comments in a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_repo_comments(owner: str, repo: str, since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all comments in a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        since: if provided, only comments updated since the provided time are returned. ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: if provided, only comments updated before the provided time are returned. ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_repo_comments', get_user_token(), **args)
    return {'issue_comments': json_to_toon(data)}

@mcp.tool(
    name='issue_delete_comment',
    description='Delete a comment',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_comment(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a comment

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of comment to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_comment', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_comment',
    description='Get a comment',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_comment(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a comment

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the comment
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_comment', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_edit_comment',
    description='Edit a comment',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_edit_comment(owner: str, repo: str, id: int, body: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a comment

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the comment to edit
        body: body field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args['body'] = body
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_comment', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_comment_reaction',
    description='Remove a reaction from a comment of an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_comment_reaction(owner: str, repo: str, id: int, content: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a reaction from a comment of an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the comment to edit
        content: The reaction content (e.g., emoji or reaction type)
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if content != "": args['content'] = content
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_comment_reaction', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_comment_reactions',
    description='Get a list of reactions from a comment of an issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_comment_reactions(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a list of reactions from a comment of an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the comment to edit
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_comment_reactions', get_user_token(), **args)
    return {'issue_comments': json_to_toon(data)}

@mcp.tool(
    name='issue_post_comment_reaction',
    description='Add a reaction to a comment of an issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_post_comment_reaction(owner: str, repo: str, id: int, content: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a reaction to a comment of an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the comment to edit
        content: The reaction content (e.g., emoji or reaction type)
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if content != "": args['content'] = content
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_post_comment_reaction', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_pinned_issues',
    description="List a repo's pinned issues",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_pinned_issues(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's pinned issues

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pinned_issues', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_delete',
    description='Delete an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of issue to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_issue',
    description='Get an issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_issue(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_edit_issue',
    description='Edit an issue. If using deadline only the date will be taken into account, and time of day ignored.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_edit_issue(owner: str, repo: str, index: int, assignee: str = '', assignees: Optional[list[str]] = None, body: str = '', due_date: str = '', milestone: int = 0, ref: str = '', state: str = '', title: str = '', unset_due_date: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit an issue. If using deadline only the date will be taken into account, and time of day ignored.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to edit
        assignee: deprecated
        assignees: assignees field
        body: body field
        due_date: due_date field ISO 8601 format (2026-06-22T15:00:00-04:00).
        milestone: milestone field
        ref: ref field
        state: state field
        title: title field
        unset_due_date: unset_due_date field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if assignee != "": args['assignee'] = assignee
    if assignees is not None: args['assignees'] = assignees
    if body != "": args['body'] = body
    if due_date != "": args['due_date'] = due_date
    if milestone != 0: args['milestone'] = milestone
    if ref != "": args['ref'] = ref
    if state != "": args['state'] = state
    if title != "": args['title'] = title
    if unset_due_date: args['unset_due_date'] = unset_due_date
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_remove_issue_blocking',
    description='Unblock the issue given in the body by the issue in path',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_remove_issue_blocking(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unblock the issue given in the body by the issue in path

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        body_index: index field
        body_owner: owner of the issue's repo
        body_repo: repo field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if body_index != 0: args['body_index'] = body_index
    if body_owner != "": args['body_owner'] = body_owner
    if body_repo != "": args['body_repo'] = body_repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_remove_issue_blocking', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_list_blocks',
    description='List issues that are blocked by this issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_list_blocks(owner: str, repo: str, index: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List issues that are blocked by this issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_list_blocks', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_create_issue_blocking',
    description='Block the issue given in the body by the issue in path',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_create_issue_blocking(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Block the issue given in the body by the issue in path

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        body_index: index field
        body_owner: owner of the issue's repo
        body_repo: repo field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if body_index != 0: args['body_index'] = body_index
    if body_owner != "": args['body_owner'] = body_owner
    if body_repo != "": args['body_repo'] = body_repo
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_issue_blocking', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_comments',
    description='List all comments on an issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_comments(owner: str, repo: str, index: int, since: str = "", before: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all comments on an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        since: if provided, only comments updated since the specified time are returned. ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: if provided, only comments updated before the provided time are returned. ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_comments', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_create_comment',
    description='Add a comment to an issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_create_comment(owner: str, repo: str, index: int, body: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a comment to an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        body: body field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['body'] = body
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_comment', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_comment_deprecated',
    description='Delete a comment',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_comment_deprecated(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a comment

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: this parameter is ignored
        id: id of comment to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_comment_deprecated', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_edit_comment_deprecated',
    description='Edit a comment',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_edit_comment_deprecated(owner: str, repo: str, index: int, id: int, body: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a comment

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: this parameter is ignored
        id: id of the comment to edit
        body: body field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    args['body'] = body
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_comment_deprecated', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_edit_issue_deadline',
    description='Set an issue deadline. If set to null, the deadline is deleted. If using deadline only the date will be taken into account, and time of day ignored.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_edit_issue_deadline(owner: str, repo: str, index: int, due_date: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Set an issue deadline. If set to null, the deadline is deleted. If using deadline only the date will be taken into account, and time of day ignored.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to create or update a deadline on
        due_date: due_date field ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['due_date'] = due_date
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_issue_deadline', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_remove_issue_dependencies',
    description='Remove an issue dependency',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_remove_issue_dependencies(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove an issue dependency

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        body_index: index field
        body_owner: owner of the issue's repo
        body_repo: repo field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if body_index != 0: args['body_index'] = body_index
    if body_owner != "": args['body_owner'] = body_owner
    if body_repo != "": args['body_repo'] = body_repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_remove_issue_dependencies', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_list_issue_dependencies',
    description="List an issue's dependencies, i.e all issues that block this issue.",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_list_issue_dependencies(owner: str, repo: str, index: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an issue's dependencies, i.e all issues that block this issue.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_list_issue_dependencies', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_create_issue_dependencies',
    description='Make the issue in the url depend on the issue in the form.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_create_issue_dependencies(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Make the issue in the url depend on the issue in the form.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        body_index: index field
        body_owner: owner of the issue's repo
        body_repo: repo field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if body_index != 0: args['body_index'] = body_index
    if body_owner != "": args['body_owner'] = body_owner
    if body_repo != "": args['body_repo'] = body_repo
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_issue_dependencies', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_clear_labels',
    description='Remove all labels from an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_clear_labels(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove all labels from an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_clear_labels', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_labels',
    description="Get an issue's labels",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_labels(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get an issue's labels

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_labels', get_user_token(), **args)
    return {'labels': json_to_toon(data)}

@mcp.tool(
    name='issue_add_label',
    description='Add a label to an issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_add_label(owner: str, repo: str, index: int, labels: Optional[list[Any]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a label to an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        labels: Labels can be a list of integers representing label IDs or a list of strings representing label names
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if labels is not None: args['labels'] = labels
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_add_label', get_user_token(), **args)
    return {'labels': json_to_toon(data)}

@mcp.tool(
    name='issue_replace_labels',
    description="Replace an issue's labels",
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_replace_labels(owner: str, repo: str, index: int, labels: Optional[list[Any]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Replace an issue's labels

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        labels: Labels can be a list of integers representing label IDs or a list of strings representing label names
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if labels is not None: args['labels'] = labels
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_replace_labels', get_user_token(), **args)
    return {'labels': json_to_toon(data)}

@mcp.tool(
    name='issue_remove_label',
    description='Remove a label from an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_remove_label(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a label from an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        id: id of the label to remove
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_remove_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_unlock_issue',
    description='Unlock an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_unlock_issue(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unlock an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_unlock_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_lock_issue',
    description='Lock an issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_lock_issue(owner: str, repo: str, index: int, lock_reason: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Lock an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        lock_reason: lock_reason field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if lock_reason != "": args['lock_reason'] = lock_reason
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_lock_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='unpin_issue',
    description='Unpin an Issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def unpin_issue(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unpin an Issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of issue to unpin
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('unpin_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='pin_issue',
    description='Pin an Issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def pin_issue(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Pin an Issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of issue to pin
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('pin_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='move_issue_pin',
    description='Moves the Pin to the given Position',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def move_issue_pin(owner: str, repo: str, index: int, position: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Moves the Pin to the given Position

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of issue
        position: the new position
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['position'] = position
    if sudo: args["sudo"] = sudo
    data = await get_client().call('move_issue_pin', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_issue_reaction',
    description='Remove a reaction from an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_issue_reaction(owner: str, repo: str, index: int, content: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a reaction from an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        content: The reaction content (e.g., emoji or reaction type)
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if content != "": args['content'] = content
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_issue_reaction', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_issue_reactions',
    description='Get a list reactions of an issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_issue_reactions(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a list reactions of an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_issue_reactions', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_post_issue_reaction',
    description='Add a reaction to an issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_post_issue_reaction(owner: str, repo: str, index: int, content: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a reaction to an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        content: The reaction content (e.g., emoji or reaction type)
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if content != "": args['content'] = content
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_post_issue_reaction', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_stop_watch',
    description="Delete an issue's existing stopwatch.",
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_stop_watch(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete an issue's existing stopwatch.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to stop the stopwatch on
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_stop_watch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_start_stop_watch',
    description='Start stopwatch on an issue.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_start_stop_watch(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Start stopwatch on an issue.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to create the stopwatch on
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_start_stop_watch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_stop_stop_watch',
    description="Stop an issue's existing stopwatch.",
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_stop_stop_watch(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Stop an issue's existing stopwatch.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to stop the stopwatch on
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_stop_stop_watch', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_subscriptions',
    description='Get users who subscribed on an issue.',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_subscriptions(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get users who subscribed on an issue.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_subscriptions', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_check_subscription',
    description='Check if user is subscribed to an issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_check_subscription(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if user is subscribed to an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_check_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_subscription',
    description='Unsubscribe user from issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_subscription(owner: str, repo: str, index: int, user: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unsubscribe user from issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        user: username of the user to unsubscribe from an issue
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['user'] = user
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_add_subscription',
    description='Subscribe user to issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_add_subscription(owner: str, repo: str, index: int, user: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Subscribe user to issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        user: username of the user to subscribe the issue to
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['user'] = user
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_add_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_comments_and_timeline',
    description='List all comments and events on an issue',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_comments_and_timeline(owner: str, repo: str, index: int, since: str = "", page: int = 1, limit: int = 50, before: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all comments and events on an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        since: if provided, only comments updated since the specified time are returned. ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: page number of results to return (1-based)
        limit: page size of results
        before: if provided, only comments updated before the provided time are returned. ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if since is not None and since != "": args['since'] = since
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if before is not None and before != "": args['before'] = before
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_comments_and_timeline', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    name='issue_reset_time',
    description='Reset a tracked time of an issue',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_reset_time(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Reset a tracked time of an issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue to add tracked time to
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_reset_time', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_tracked_times',
    description="List an issue's tracked times",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_tracked_times(owner: str, repo: str, index: int, user: str = "", since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an issue's tracked times

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        user: optional filter by user (available for issue managers)
        since: Only show times updated after the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show times updated before the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if user is not None and user != "": args['user'] = user
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_tracked_times', get_user_token(), **args)
    return {'tracked_times': json_to_toon(data)}

@mcp.tool(
    name='issue_add_time',
    description='Add tracked time to a issue',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_add_time(owner: str, repo: str, index: int, time: int, created: str = '', user_name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add tracked time to a issue

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        created: created field ISO 8601 format (2026-06-22T15:00:00-04:00).
        time: time in seconds
        user_name: username of the user who spent the time working on the issue (optional)
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if created != "": args['created'] = created
    args['time'] = time
    if user_name != "": args['user_name'] = user_name
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_add_time', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_time',
    description='Delete specific tracked time',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_time(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete specific tracked time

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the issue
        id: id of time to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_time', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_keys',
    description="List a repository's keys",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_keys(owner: str, repo: str, key_id: int = 0, fingerprint: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's keys

    Args:
        owner: owner of the repo
        repo: name of the repo
        key_id: the key_id to search for
        fingerprint: fingerprint of the key
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if key_id is not None and key_id != "": args['key_id'] = key_id
    if fingerprint is not None and fingerprint != "": args['fingerprint'] = fingerprint
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_keys', get_user_token(), **args)
    return {'deploy_keys': json_to_toon(data)}

@mcp.tool(
    name='repo_create_key',
    description='Add a key to a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_key(owner: str, repo: str, key: str, title: str, read_only: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a key to a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        key: An armored SSH key to add
        read_only: Describe if the key has only read access or read/write
        title: Title of the key to add
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['key'] = key
    if read_only: args['read_only'] = read_only
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_key', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_key',
    description='Delete a key from a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_key(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a key from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the key to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_key', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_key',
    description="Get a repository's key by id",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_key(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a repository's key by id

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the key to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_key', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_list_labels',
    description="Get all of a repository's labels",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_list_labels(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get all of a repository's labels

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_list_labels', get_user_token(), **args)
    return {'labels': json_to_toon(data)}

@mcp.tool(
    name='issue_create_label',
    description='Create a label',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_create_label(owner: str, repo: str, color: str, description: str, name: str, exclusive: bool = False, is_archived: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a label

    Args:
        owner: owner of the repo
        repo: name of the repo
        color: color field
        description: Description provides additional context about the label's purpose
        exclusive: exclusive field
        is_archived: is_archived field
        name: name field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['color'] = color
    args['description'] = description
    if exclusive: args['exclusive'] = exclusive
    if is_archived: args['is_archived'] = is_archived
    args['name'] = name
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_label',
    description='Delete a label',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_label(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a label

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the label to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_label',
    description='Get a single label',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_label(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a single label

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the label to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_edit_label',
    description='Update a label',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_edit_label(owner: str, repo: str, id: int, color: str = '', description: str = '', exclusive: bool = False, is_archived: bool = False, name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a label

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the label to edit
        color: color field
        description: Description provides additional context about the label's purpose
        exclusive: exclusive field
        is_archived: is_archived field
        name: Name is the new display name for the label
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if color != "": args['color'] = color
    if description != "": args['description'] = description
    if exclusive: args['exclusive'] = exclusive
    if is_archived: args['is_archived'] = is_archived
    if name != "": args['name'] = name
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_languages',
    description='Get languages and number of bytes of code written',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_languages(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get languages and number of bytes of code written

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_languages', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_licenses',
    description='Get repo licenses',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_licenses(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get repo licenses

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_licenses', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='repo_merge_upstream',
    description='Merge a branch from upstream',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_merge_upstream(owner: str, repo: str, branch: str = '', ff_only: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Merge a branch from upstream

    Args:
        owner: owner of the repo
        repo: name of the repo
        branch: branch field
        ff_only: ff_only field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if branch != "": args['branch'] = branch
    if ff_only: args['ff_only'] = ff_only
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_merge_upstream', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_milestones_list',
    description="Get all of a repository's opened milestones",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_milestones_list(owner: str, repo: str, state: str = "", name: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get all of a repository's opened milestones

    Args:
        owner: owner of the repo
        repo: name of the repo
        state: Milestone state, Recognized values are open, closed and all. Defaults to "open"
        name: filter by milestone name
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if state is not None and state != "": args['state'] = state
    if name is not None and name != "": args['name'] = name
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_milestones_list', get_user_token(), **args)
    return {'milestones': json_to_toon(data)}

@mcp.tool(
    name='issue_create_milestone',
    description='Create a milestone',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def issue_create_milestone(owner: str, repo: str, description: str, title: str, due_on: str = '', state: Optional[Literal['open', 'closed']] = 'open', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a milestone

    Args:
        owner: owner of the repo
        repo: name of the repo
        description: Description provides details about the milestone
        due_on: due_on field ISO 8601 format (2026-06-22T15:00:00-04:00).
        state: state field
        title: Title is the title of the new milestone
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['description'] = description
    if due_on != "": args['due_on'] = due_on
    if state is not None: args['state'] = state
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_milestone', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_delete_milestone',
    description='Delete a milestone',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def issue_delete_milestone(owner: str, repo: str, id: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a milestone

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: the milestone to delete, identified by ID and if not available by name
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_delete_milestone', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_get_milestone',
    description='Get a milestone',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_get_milestone(owner: str, repo: str, id: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a milestone

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: the milestone to get, identified by ID and if not available by name
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_get_milestone', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='issue_edit_milestone',
    description='Update a milestone',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def issue_edit_milestone(owner: str, repo: str, id: str, description: str = '', due_on: str = '', state: str = '', title: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a milestone

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: the milestone to edit, identified by ID and if not available by name
        description: Description provides updated details about the milestone
        due_on: Deadline is the updated due date for the milestone ISO 8601 format (2026-06-22T15:00:00-04:00).
        state: State indicates the updated state of the milestone
        title: Title is the updated title of the milestone
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if description != "": args['description'] = description
    if due_on != "": args['due_on'] = due_on
    if state != "": args['state'] = state
    if title != "": args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_milestone', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='notify_get_repo_list',
    description="List users's notification threads on a specific repo",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_get_repo_list(owner: str, repo: str, all: bool = False, status_types: Optional[list[str]] = None, subject_type: Optional[list[Literal['issue', 'pull', 'commit', 'repository']]] = None, since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List users's notification threads on a specific repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        all: If true, show notifications marked as read. Default value is false
        status_types: Show notifications with the provided status types. Options are: unread, read and/or pinned. Defaults to unread & pinned
        subject_type: filter notifications by subject type
        since: Only show notifications updated after the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show notifications updated before the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status-types'] = status_types
    if subject_type is not None and subject_type != "": args['subject-type'] = subject_type
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_get_repo_list', get_user_token(), **args)
    return {'notifications': json_to_toon(data)}

@mcp.tool(
    name='notify_read_repo_list',
    description='Mark notification threads as read, pinned or unread on a specific repo',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def notify_read_repo_list(owner: str, repo: str, all: str = "", status_types: Optional[list[str]] = None, to_status: str = "", last_read_at: str = "", sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Mark notification threads as read, pinned or unread on a specific repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        all: If true, mark all notifications on this repo. Default value is false
        status_types: Mark notifications with the provided status types. Options are: unread, read and/or pinned. Defaults to unread.
        to_status: Status to mark notifications as. Defaults to read.
        last_read_at: Describes the last point that notifications were checked. Anything updated since this time will not be updated. ISO 8601 format (2026-06-22T15:00:00-04:00).
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status-types'] = status_types
    if to_status is not None and to_status != "": args['to-status'] = to_status
    if last_read_at is not None and last_read_at != "": args['last_read_at'] = last_read_at
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_read_repo_list', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_pull_requests',
    description="List a repo's pull requests",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_pull_requests(owner: str, repo: str, base_branch: str = "", state: Literal['open', 'closed', 'all'] = 'open', sort: Literal['oldest', 'recentupdate', 'recentclose', 'leastupdate', 'mostcomment', 'leastcomment', 'priority'] = 'oldest', milestone: int = 0, labels: Optional[list[int]] = None, poster: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's pull requests

    Args:
        owner: owner of the repo
        repo: Name of the repo
        base_branch: Filter by target base branch of the pull request
        state: State of pull request
        sort: Type of sort
        milestone: ID of the milestone
        labels: Label IDs
        poster: Filter by pull request author
        page: Page number of results to return (1-based)
        limit: Page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if base_branch is not None and base_branch != "": args['base_branch'] = base_branch
    if state is not None and state != "": args['state'] = state
    if sort is not None and sort != "": args['sort'] = sort
    if milestone is not None and milestone != "": args['milestone'] = milestone
    if labels is not None and labels != "": args['labels'] = labels
    if poster is not None and poster != "": args['poster'] = poster
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pull_requests', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    name='repo_create_pull_request',
    description='Create a pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_pull_request(owner: str, repo: str, base: str, body: str, head: str, title: str, assignee: str = '', assignees: Optional[list[str]] = None, due_date: str = '', labels: Optional[list[int]] = None, milestone: int = 0, reviewers: Optional[list[str]] = None, team_reviewers: Optional[list[str]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        assignee: The primary assignee username
        assignees: The list of assignee usernames
        base: The base branch for the pull request
        body: The description body of the pull request
        due_date: due_date field ISO 8601 format (2026-06-22T15:00:00-04:00).
        head: The head branch for the pull request, it could be a branch name on the base repository or a form like `<username>:<branch>` which refers to the user's fork repository's branch.
        labels: The list of label IDs to assign to the pull request
        milestone: The milestone ID to assign to the pull request
        reviewers: The list of reviewer usernames
        team_reviewers: The list of team reviewer names
        title: The title of the pull request
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if assignee != "": args['assignee'] = assignee
    if assignees is not None: args['assignees'] = assignees
    args['base'] = base
    args['body'] = body
    if due_date != "": args['due_date'] = due_date
    args['head'] = head
    if labels is not None: args['labels'] = labels
    if milestone != 0: args['milestone'] = milestone
    if reviewers is not None: args['reviewers'] = reviewers
    if team_reviewers is not None: args['team_reviewers'] = team_reviewers
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_pinned_pull_requests',
    description="List a repo's pinned pull requests",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_pinned_pull_requests(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's pinned pull requests

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pinned_pull_requests', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    name='repo_get_pull_request_by_base_head',
    description='Get a pull request by base and head',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_pull_request_by_base_head(owner: str, repo: str, base: str, head: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a pull request by base and head

    Args:
        owner: owner of the repo
        repo: name of the repo
        base: base of the pull request to get
        head: head of the pull request to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['base'] = base
    args['head'] = head
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_request_by_base_head', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_pull_request',
    description='Get a pull request',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_pull_request(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_edit_pull_request',
    description='Update a pull request. If using deadline only the date will be taken into account, and time of day ignored.',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_edit_pull_request(owner: str, repo: str, index: int, allow_maintainer_edit: bool = False, assignee: str = '', assignees: Optional[list[str]] = None, base: str = '', body: str = '', due_date: str = '', labels: Optional[list[int]] = None, milestone: int = 0, state: str = '', title: str = '', unset_due_date: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a pull request. If using deadline only the date will be taken into account, and time of day ignored.

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to edit
        allow_maintainer_edit: Whether to allow maintainer edits
        assignee: The new primary assignee username
        assignees: The new list of assignee usernames
        base: The new base branch for the pull request
        body: The new description body for the pull request
        due_date: due_date field ISO 8601 format (2026-06-22T15:00:00-04:00).
        labels: The new list of label IDs for the pull request
        milestone: The new milestone ID for the pull request
        state: The new state for the pull request
        title: The new title for the pull request
        unset_due_date: Whether to remove the current deadline
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if allow_maintainer_edit: args['allow_maintainer_edit'] = allow_maintainer_edit
    if assignee != "": args['assignee'] = assignee
    if assignees is not None: args['assignees'] = assignees
    if base != "": args['base'] = base
    if body != "": args['body'] = body
    if due_date != "": args['due_date'] = due_date
    if labels is not None: args['labels'] = labels
    if milestone != 0: args['milestone'] = milestone
    if state != "": args['state'] = state
    if title != "": args['title'] = title
    if unset_due_date: args['unset_due_date'] = unset_due_date
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_pull_request_commits',
    description='Get commits for a pull request',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_pull_request_commits(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, verification: bool = False, files: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get commits for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to get
        page: page number of results to return (1-based)
        limit: page size of results
        verification: include verification for every commit (disable for speedup, default 'true')
        files: include a list of affected files for every commit (disable for speedup, default 'true')
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if verification is not None and verification != "": args['verification'] = verification
    if files is not None and files != "": args['files'] = files
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_request_commits', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    name='repo_get_pull_request_files',
    description='Get changed files for a pull request',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_pull_request_files(owner: str, repo: str, index: int, skip_to: str = "", whitespace: Literal['ignore-all', 'ignore-change', 'ignore-eol', 'show-all'] = 'ignore-all', page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get changed files for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to get
        skip_to: skip to given file
        whitespace: whitespace behavior
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if skip_to is not None and skip_to != "": args['skip-to'] = skip_to
    if whitespace is not None and whitespace != "": args['whitespace'] = whitespace
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_request_files', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    name='repo_cancel_scheduled_auto_merge',
    description='Cancel the scheduled auto merge for the given pull request',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_cancel_scheduled_auto_merge(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Cancel the scheduled auto merge for the given pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to merge
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_cancel_scheduled_auto_merge', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_pull_request_is_merged',
    description='Check if a pull request has been merged',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_pull_request_is_merged(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a pull request has been merged

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_pull_request_is_merged', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_merge_pull_request',
    description='Merge a pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_merge_pull_request(owner: str, repo: str, index: int, Do: Literal['merge', 'rebase', 'rebase-merge', 'squash', 'fast-forward-only', 'manually-merged'], MergeCommitID: str = '', MergeMessageField: str = '', MergeTitleField: str = '', delete_branch_after_merge: bool = False, force_merge: bool = False, head_commit_id: str = '', merge_when_checks_succeed: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Merge a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to merge
        Do: Do field
        MergeCommitID: MergeCommitID field
        MergeMessageField: MergeMessageField field
        MergeTitleField: MergeTitleField field
        delete_branch_after_merge: delete_branch_after_merge field
        force_merge: force_merge field
        head_commit_id: head_commit_id field
        merge_when_checks_succeed: merge_when_checks_succeed field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['Do'] = Do
    if MergeCommitID != "": args['MergeCommitID'] = MergeCommitID
    if MergeMessageField != "": args['MergeMessageField'] = MergeMessageField
    if MergeTitleField != "": args['MergeTitleField'] = MergeTitleField
    if delete_branch_after_merge: args['delete_branch_after_merge'] = delete_branch_after_merge
    if force_merge: args['force_merge'] = force_merge
    if head_commit_id != "": args['head_commit_id'] = head_commit_id
    if merge_when_checks_succeed: args['merge_when_checks_succeed'] = merge_when_checks_succeed
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_merge_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_pull_review_requests',
    description='cancel review requests for a pull request',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_pull_review_requests(owner: str, repo: str, index: int, reviewers: Optional[list[str]] = None, team_reviewers: Optional[list[str]] = None, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """cancel review requests for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        reviewers: reviewers field
        team_reviewers: team_reviewers field
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if reviewers is not None: args['reviewers'] = reviewers
    if team_reviewers is not None: args['team_reviewers'] = team_reviewers
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_pull_review_requests', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_create_pull_review_requests',
    description='create review requests for a pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_pull_review_requests(owner: str, repo: str, index: int, reviewers: Optional[list[str]] = None, team_reviewers: Optional[list[str]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """create review requests for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        reviewers: reviewers field
        team_reviewers: team_reviewers field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if reviewers is not None: args['reviewers'] = reviewers
    if team_reviewers is not None: args['team_reviewers'] = team_reviewers
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_pull_review_requests', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    name='repo_list_pull_reviews',
    description='List all reviews for a pull request',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_pull_reviews(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all reviews for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pull_reviews', get_user_token(), **args)
    return {'pull_reviews': json_to_toon(data)}

@mcp.tool(
    name='repo_create_pull_review',
    description='Create a review to an pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_pull_review(owner: str, repo: str, index: int, body: str, event: str, comments: Optional[list[CreatePullReviewComment]] = None, commit_id: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a review to an pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        body: body field
        comments: comments field
        commit_id: commit_id field
        event: event field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['body'] = body
    if comments is not None: args['comments'] = comments
    if commit_id != "": args['commit_id'] = commit_id
    args['event'] = event
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_pull_review',
    description='Delete a specific review from a pull request',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_pull_review(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific review from a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        id: id of the review
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_pull_review',
    description='Get a specific review for a pull request',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_pull_review(owner: str, repo: str, index: int, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific review for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        id: id of the review
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_submit_pull_review',
    description='Submit a pending review to an pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_submit_pull_review(owner: str, repo: str, index: int, id: int, body: str = '', event: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Submit a pending review to an pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        id: id of the review
        body: body field
        event: event field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if body != "": args['body'] = body
    if event != "": args['event'] = event
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_submit_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_pull_review_comments',
    description='Get a specific review for a pull request',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_pull_review_comments(owner: str, repo: str, index: int, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific review for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        id: id of the review
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_review_comments', get_user_token(), **args)
    return {'pull_review_comments': json_to_toon(data)}

@mcp.tool(
    name='repo_dismiss_pull_review',
    description='Dismiss a review for a pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_dismiss_pull_review(owner: str, repo: str, index: int, id: int, message: str = '', priors: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Dismiss a review for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        id: id of the review
        message: message field
        priors: priors field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if message != "": args['message'] = message
    if priors: args['priors'] = priors
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_dismiss_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_un_dismiss_pull_review',
    description='Cancel to dismiss a review for a pull request',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_un_dismiss_pull_review(owner: str, repo: str, index: int, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Cancel to dismiss a review for a pull request

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request
        id: id of the review
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_un_dismiss_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_update_pull_request',
    description="Merge PR's baseBranch into headBranch",
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_update_pull_request(owner: str, repo: str, index: int, style: Literal['merge', 'rebase'] = 'merge', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Merge PR's baseBranch into headBranch

    Args:
        owner: owner of the repo
        repo: name of the repo
        index: index of the pull request to get
        style: how to update pull request
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if style is not None and style != "": args['style'] = style
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_update_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_releases',
    description="List a repo's releases",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_releases(owner: str, repo: str, draft: bool = False, pre_release: bool = False, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's releases

    Args:
        owner: owner of the repo
        repo: name of the repo
        draft: filter (exclude / include) drafts, if you dont have repo write access none will show
        pre_release: filter (exclude / include) pre-releases
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if draft is not None and draft != "": args['draft'] = draft
    if pre_release is not None and pre_release != "": args['pre-release'] = pre_release
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_releases', get_user_token(), **args)
    return {'releases': json_to_toon(data)}

@mcp.tool(
    name='repo_create_release',
    description='Create a release',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_release(owner: str, repo: str, body: str, tag_name: str, draft: bool = False, name: str = '', prerelease: bool = False, tag_message: str = '', target_commitish: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a release

    Args:
        owner: owner of the repo
        repo: name of the repo
        body: The release notes or description
        draft: Whether to create the release as a draft
        name: The display title of the release
        prerelease: Whether to mark the release as a prerelease
        tag_message: The message for the git tag
        tag_name: tag_name field
        target_commitish: The target commitish for the release
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['body'] = body
    if draft: args['draft'] = draft
    if name != "": args['name'] = name
    if prerelease: args['prerelease'] = prerelease
    if tag_message != "": args['tag_message'] = tag_message
    args['tag_name'] = tag_name
    if target_commitish != "": args['target_commitish'] = target_commitish
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_release', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_latest_release',
    description='Gets the most recent non-prerelease, non-draft release of a repository, sorted by created_at',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_latest_release(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the most recent non-prerelease, non-draft release of a repository, sorted by created_at

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_latest_release', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_release_by_tag',
    description='Delete a release by tag name',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_release_by_tag(owner: str, repo: str, tag: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a release by tag name

    Args:
        owner: owner of the repo
        repo: name of the repo
        tag: tag name of the release to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['tag'] = tag
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_release_by_tag', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_release_by_tag',
    description='Get a release by tag name',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_release_by_tag(owner: str, repo: str, tag: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a release by tag name

    Args:
        owner: owner of the repo
        repo: name of the repo
        tag: tag name of the release to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['tag'] = tag
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_release_by_tag', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_release',
    description='Delete a release',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_release(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a release

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the release to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_release', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_release',
    description='Get a release',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_release(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a release

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the release to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_release', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_edit_release',
    description='Update a release',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_edit_release(owner: str, repo: str, id: int, body: str = '', draft: bool = False, name: str = '', prerelease: bool = False, tag_name: str = '', target_commitish: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a release

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the release to edit
        body: The new release notes or description
        draft: Whether to change the draft status
        name: The new display title of the release
        prerelease: Whether to change the prerelease status
        tag_name: The new name of the git tag
        target_commitish: The new target commitish for the release
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if body != "": args['body'] = body
    if draft: args['draft'] = draft
    if name != "": args['name'] = name
    if prerelease: args['prerelease'] = prerelease
    if tag_name != "": args['tag_name'] = tag_name
    if target_commitish != "": args['target_commitish'] = target_commitish
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_release', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_reviewers',
    description='Return all users that can be requested to review in this repo',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_reviewers(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Return all users that can be requested to review in this repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_reviewers', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    name='repo_list_statuses',
    description="Get a commit's statuses",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_statuses(owner: str, repo: str, sha: str, sort: Literal['oldest', 'recentupdate', 'leastupdate', 'leastindex', 'highestindex'] = 'oldest', state: Literal['pending', 'success', 'error', 'failure', 'warning'] = 'pending', page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a commit's statuses

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: sha of the commit
        sort: type of sort
        state: type of state
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    if sort is not None and sort != "": args['sort'] = sort
    if state is not None and state != "": args['state'] = state
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_statuses', get_user_token(), **args)
    return {'commit_statuses': json_to_toon(data)}

@mcp.tool(
    name='repo_create_status',
    description='Create a commit status',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_status(owner: str, repo: str, sha: str, state: Literal['pending', 'success', 'error', 'failure', 'warning', 'skipped'], context: str = '', description: str = '', target_url: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a commit status

    Args:
        owner: owner of the repo
        repo: name of the repo
        sha: sha of the commit
        context: Context is the unique context identifier for the status
        description: Description provides a brief description of the status
        state: State represents the status state to set (pending, success, error, failure) pending CommitStatusPending  CommitStatusPending is for when the CommitStatus is Pending success CommitStatusSuccess  CommitStatusSuccess is for when the CommitStatus is Success error CommitStatusError  CommitStatusError is for when the CommitStatus is Error failure CommitStatusFailure  CommitStatusFailure is for when the CommitStatus is Failure warning CommitStatusWarning  CommitStatusWarning is for when the CommitStatus is Warning skipped CommitStatusSkipped  CommitStatusSkipped is for when CommitStatus is Skipped
        target_url: TargetURL is the URL to link to for more details
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    if context != "": args['context'] = context
    if description != "": args['description'] = description
    args['state'] = state
    if target_url != "": args['target_url'] = target_url
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_status', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_delete_subscription',
    description='Unwatch a repo',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def user_current_delete_subscription(owner: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unwatch a repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_delete_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_check_subscription',
    description='Check if the current user is watching a repo',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_check_subscription(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if the current user is watching a repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_check_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_put_subscription',
    description='Watch a repo',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_put_subscription(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Watch a repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_put_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_tag_protection',
    description='List tag protections for a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_tag_protection(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List tag protections for a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_tag_protection', get_user_token(), **args)
    return {'tag_protections': json_to_toon(data)}

@mcp.tool(
    name='repo_create_tag_protection',
    description='Create a tag protections for a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_tag_protection(owner: str, repo: str, name_pattern: str, whitelist_teams: Optional[list[str]] = None, whitelist_usernames: Optional[list[str]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a tag protections for a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        name_pattern: The pattern to match tag names for protection
        whitelist_teams: List of team names allowed to create/delete protected tags
        whitelist_usernames: List of usernames allowed to create/delete protected tags
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['name_pattern'] = name_pattern
    if whitelist_teams is not None: args['whitelist_teams'] = whitelist_teams
    if whitelist_usernames is not None: args['whitelist_usernames'] = whitelist_usernames
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_tag_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_tag_protection',
    description='Delete a specific tag protection for the repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_tag_protection(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific tag protection for the repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of protected tag
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_tag_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_tag_protection',
    description='Get a specific tag protection for the repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_tag_protection(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific tag protection for the repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of the tag protect to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_tag_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_edit_tag_protection',
    description='Edit a tag protections for a repository. Only fields that are set will be changed',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_edit_tag_protection(owner: str, repo: str, id: int, name_pattern: str = '', whitelist_teams: Optional[list[str]] = None, whitelist_usernames: Optional[list[str]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a tag protections for a repository. Only fields that are set will be changed

    Args:
        owner: owner of the repo
        repo: name of the repo
        id: id of protected tag
        name_pattern: The pattern to match tag names for protection
        whitelist_teams: List of team names allowed to create/delete protected tags
        whitelist_usernames: List of usernames allowed to create/delete protected tags
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if name_pattern != "": args['name_pattern'] = name_pattern
    if whitelist_teams is not None: args['whitelist_teams'] = whitelist_teams
    if whitelist_usernames is not None: args['whitelist_usernames'] = whitelist_usernames
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_tag_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_tags',
    description="List a repository's tags",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_tags(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's tags

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results, default maximum page size is 50
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_tags', get_user_token(), **args)
    return {'tags': json_to_toon(data)}

@mcp.tool(
    name='repo_create_tag',
    description='Create a new git tag in a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_tag(owner: str, repo: str, tag_name: str, message: str = '', target: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a new git tag in a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        message: The message to associate with the tag
        tag_name: tag_name field
        target: The target commit SHA or branch name for the tag
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if message != "": args['message'] = message
    args['tag_name'] = tag_name
    if target != "": args['target'] = target
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_tag', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_tag',
    description="Delete a repository's tag by name",
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_tag(owner: str, repo: str, tag: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a repository's tag by name

    Args:
        owner: owner of the repo
        repo: name of the repo
        tag: name of tag to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['tag'] = tag
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_tag', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_tag',
    description='Get the tag of a repository by tag name',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_tag(owner: str, repo: str, tag: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get the tag of a repository by tag name

    Args:
        owner: owner of the repo
        repo: name of the repo
        tag: name of tag
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['tag'] = tag
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_tag', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_list_teams',
    description="List a repository's teams",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_teams(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's teams

    Args:
        owner: owner of the repo
        repo: name of the repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_teams', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    name='repo_delete_team',
    description='Delete a team from a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_team(owner: str, repo: str, team: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a team from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        team: team name
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['team'] = team
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_check_team',
    description='Check if a team is assigned to a repository',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_check_team(owner: str, repo: str, team: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a team is assigned to a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        team: team name
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['team'] = team
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_check_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_add_team',
    description='Add a team to a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_add_team(owner: str, repo: str, team: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a team to a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        team: team name
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['team'] = team
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_add_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_tracked_times',
    description="List a repo's tracked times",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_tracked_times(owner: str, repo: str, user: str = "", since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's tracked times

    Args:
        owner: owner of the repo
        repo: name of the repo
        user: optional filter by user (available for issue managers)
        since: Only show times updated after the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show times updated before the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if user is not None and user != "": args['user'] = user
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_tracked_times', get_user_token(), **args)
    return {'tracked_times': json_to_toon(data)}

@mcp.tool(
    name='user_tracked_times',
    description="List a user's tracked times in a repo",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_tracked_times(owner: str, repo: str, user: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a user's tracked times in a repo

    Args:
        owner: owner of the repo
        repo: name of the repo
        user: username of the user whose tracked times are to be listed
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['user'] = user
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_tracked_times', get_user_token(), **args)
    return {'tracked_times': json_to_toon(data)}

@mcp.tool(
    name='repo_list_topics',
    description='Get list of topics that a repository has',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_list_topics(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get list of topics that a repository has

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_topics', get_user_token(), **args)
    return {'topics': json_to_toon(data)}

@mcp.tool(
    name='repo_update_topics',
    description='Replace list of topics for a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_update_topics(owner: str, repo: str, topics: Optional[list[str]] = None, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Replace list of topics for a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        topics: list of topic names
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if topics is not None: args['topics'] = topics
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_update_topics', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_topic',
    description='Delete a topic from a repository',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_topic(owner: str, repo: str, topic: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a topic from a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        topic: name of the topic to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['topic'] = topic
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_topic', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_add_topic',
    description='Add a topic to a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_add_topic(owner: str, repo: str, topic: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a topic to a repository

    Args:
        owner: owner of the repo
        repo: name of the repo
        topic: name of the topic to add
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['topic'] = topic
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_add_topic', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_create_wiki_page',
    description='Create a wiki page',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def repo_create_wiki_page(owner: str, repo: str, content_base64: str, title: str, message: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a wiki page

    Args:
        owner: owner of the repo
        repo: name of the repo
        content_base64: content must be base64 encoded
        message: optional commit message summarizing the change
        title: page title. leave empty to keep unchanged
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['content_base64'] = content_base64
    if message != "": args['message'] = message
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_wiki_page', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_delete_wiki_page',
    description='Delete a wiki page',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def repo_delete_wiki_page(owner: str, repo: str, pageName: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a wiki page

    Args:
        owner: owner of the repo
        repo: name of the repo
        pageName: name of the page
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['pageName'] = pageName
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete_wiki_page', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_wiki_page',
    description='Get a wiki page',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_wiki_page(owner: str, repo: str, pageName: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a wiki page

    Args:
        owner: owner of the repo
        repo: name of the repo
        pageName: name of the page
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['pageName'] = pageName
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_wiki_page', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_edit_wiki_page',
    description='Edit a wiki page',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_edit_wiki_page(owner: str, repo: str, pageName: str, content_base64: str = '', message: str = '', title: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a wiki page

    Args:
        owner: owner of the repo
        repo: name of the repo
        pageName: name of the page
        content_base64: content must be base64 encoded
        message: optional commit message summarizing the change
        title: page title. leave empty to keep unchanged
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['pageName'] = pageName
    if content_base64 != "": args['content_base64'] = content_base64
    if message != "": args['message'] = message
    if title != "": args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_wiki_page', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_wiki_pages',
    description='Get all wiki pages',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_wiki_pages(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get all wiki pages

    Args:
        owner: owner of the repo
        repo: name of the repo
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_wiki_pages', get_user_token(), **args)
    return {'wiki_pages': json_to_toon(data)}

@mcp.tool(
    name='repo_get_wiki_page_revisions',
    description='Get revisions of a wiki page',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_wiki_page_revisions(owner: str, repo: str, pageName: str, page: int = 1, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get revisions of a wiki page

    Args:
        owner: owner of the repo
        repo: name of the repo
        pageName: name of the page
        page: page number of results to return (1-based)
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['pageName'] = pageName
    if page is not None and page != "": args['page'] = page
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_wiki_page_revisions', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='generate_repo',
    description='Create a repository using a template',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def generate_repo(template_owner: str, template_repo: str, description: str, name: str, owner: str, avatar: bool = False, default_branch: str = '', git_content: bool = False, git_hooks: bool = False, labels: bool = False, private: bool = False, protected_branch: bool = False, topics: bool = False, webhooks: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository using a template

    Args:
        template_owner: owner of the template repository
        template_repo: name of the template repository
        avatar: include avatar of the template repo
        default_branch: Default branch of the new repository
        description: Description of the repository to create
        git_content: include git content of default branch in template repo
        git_hooks: include git hooks in template repo
        labels: include labels in template repo
        name: name field
        owner: the organization's name or individual user's name who will own the new repository
        private: Whether the repository is private
        protected_branch: include protected branches in template repo
        topics: include topics in template repo
        webhooks: include webhooks in template repo
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['template_owner'] = template_owner
    args['template_repo'] = template_repo
    if avatar: args['avatar'] = avatar
    if default_branch != "": args['default_branch'] = default_branch
    args['description'] = description
    if git_content: args['git_content'] = git_content
    if git_hooks: args['git_hooks'] = git_hooks
    if labels: args['labels'] = labels
    args['name'] = name
    args['owner'] = owner
    if private: args['private'] = private
    if protected_branch: args['protected_branch'] = protected_branch
    if topics: args['topics'] = topics
    if webhooks: args['webhooks'] = webhooks
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('generate_repo', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='repo_get_by_id',
    description='Get a repository by id',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def repo_get_by_id(id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a repository by id

    Args:
        id: id of the repo to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_by_id', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_delete_team',
    description='Delete a team',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_delete_team(id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a team

    Args:
        id: id of the team to delete
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_get_team',
    description='Get a team',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_get_team(id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a team

    Args:
        id: id of the team to get
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_edit_team',
    description='Edit a team',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_edit_team(id: int, name: str, can_create_org_repo: bool = False, description: str = '', includes_all_repositories: bool = False, permission: Optional[Literal['read', 'write', 'admin']] = 'read', units: Optional[list[str]] = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a team

    Args:
        id: id of the team to edit
        can_create_org_repo: Whether the team can create repositories in the organization
        description: The description of the team
        includes_all_repositories: Whether the team has access to all repositories in the organization
        name: name field
        permission: permission field
        units: units field
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if can_create_org_repo: args['can_create_org_repo'] = can_create_org_repo
    if description != "": args['description'] = description
    if includes_all_repositories: args['includes_all_repositories'] = includes_all_repositories
    args['name'] = name
    if permission is not None: args['permission'] = permission
    if units is not None: args['units'] = units
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_edit_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_team_activity_feeds',
    description="List a team's activity feeds",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_team_activity_feeds(id: int, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a team's activity feeds

    Args:
        id: id of the team
        date: the date of the activities to be found
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if date is not None and date != "": args['date'] = date
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_team_activity_feeds', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    name='org_list_team_members',
    description="List a team's members",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_team_members(id: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a team's members

    Args:
        id: id of the team
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_team_members', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    name='org_remove_team_member',
    description='Remove a team member',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_remove_team_member(id: int, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a team member

    Args:
        id: id of the team
        username: username of the user to remove from a team
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_remove_team_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_team_member',
    description='List a particular member of team',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_team_member(id: int, username: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a particular member of team

    Args:
        id: id of the team
        username: username of the user whose data is to be listed
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['username'] = username
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_team_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_add_team_member',
    description='Add a team member',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_add_team_member(id: int, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a team member

    Args:
        id: id of the team
        username: username of the user to add to a team
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_add_team_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_team_repos',
    description="List a team's repos",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_team_repos(id: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a team's repos

    Args:
        id: id of the team
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_team_repos', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    name='org_remove_team_repository',
    description='Remove a repository from a team',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def org_remove_team_repository(id: int, org: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a repository from a team

    Args:
        id: id of the team
        org: organization that owns the repo to remove
        repo: name of the repo to remove
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['org'] = org
    args['repo'] = repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_remove_team_repository', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_team_repo',
    description='List a particular repo of team',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_team_repo(id: int, org: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a particular repo of team

    Args:
        id: id of the team
        org: organization that owns the repo to list
        repo: name of the repo to list
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['org'] = org
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_team_repo', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_add_team_repository',
    description='Add a repository to a team',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_add_team_repository(id: int, org: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a repository to a team

    Args:
        id: id of the team
        org: organization that owns the repo to add
        repo: name of the repo to add
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['org'] = org
    args['repo'] = repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_add_team_repository', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='topic_search',
    description='search topics via keyword',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def topic_search(q: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """search topics via keyword

    Args:
        q: keywords to search
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['q'] = q
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('topic_search', get_user_token(), **args)
    return {'topics': json_to_toon(data)}

@mcp.tool(
    name='user_get_current',
    description='Get the authenticated user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_get_current(include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get the authenticated user

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get_current', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_list_followers',
    description="List the authenticated user's followers",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_list_followers(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the authenticated user's followers

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_followers', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_current_list_following',
    description='List the users that the authenticated user is following',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_list_following(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the users that the authenticated user is following

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_following', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_current_delete_follow',
    description='Unfollow a user',
    tags={"delete", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False),
)
async def user_current_delete_follow(username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unfollow a user

    Args:
        username: username of the user to unfollow
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_delete_follow', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_check_following',
    description='Check whether a user is followed by the authenticated user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_check_following(username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check whether a user is followed by the authenticated user

    Args:
        username: username of the user to check for authenticated followers
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_check_following', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_put_follow',
    description='Follow a user',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_put_follow(username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Follow a user

    Args:
        username: username of the user to follow
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_put_follow', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='org_list_current_user_orgs',
    description="List the current user's organizations",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_current_user_orgs(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the current user's organizations

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_current_user_orgs', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='user_current_list_repos',
    description='List the repos that the authenticated user owns',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_list_repos(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the repos that the authenticated user owns

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_repos', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='create_current_user_repo',
    description='Create a repository',
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def create_current_user_repo(description: str, name: str, auto_init: bool = False, default_branch: str = '', gitignores: str = '', issue_labels: str = '', license: str = '', object_format_name: Optional[Literal['sha1', 'sha256']] = 'sha1', private: bool = False, readme: str = '', template: bool = False, trust_model: Optional[Literal['default', 'collaborator', 'committer', 'collaboratorcommitter']] = 'default', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository

    Args:
        auto_init: Whether the repository should be auto-initialized?
        default_branch: DefaultBranch of the repository (used when initializes and in template)
        description: Description of the repository to create
        gitignores: Gitignores to use
        issue_labels: Label-Set to use
        license: License to use
        name: Name of the repository to create
        object_format_name: ObjectFormatName of the underlying git repository
        private: Whether the repository is private
        readme: Readme of the repository to create
        template: Whether the repository is template
        trust_model: TrustModel of the repository
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if auto_init: args['auto_init'] = auto_init
    if default_branch != "": args['default_branch'] = default_branch
    args['description'] = description
    if gitignores != "": args['gitignores'] = gitignores
    if issue_labels != "": args['issue_labels'] = issue_labels
    if license != "": args['license'] = license
    args['name'] = name
    if object_format_name is not None: args['object_format_name'] = object_format_name
    if private: args['private'] = private
    if readme != "": args['readme'] = readme
    if template: args['template'] = template
    if trust_model is not None: args['trust_model'] = trust_model
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_current_user_repo', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_current_list_starred',
    description='The repos that the authenticated user has starred',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_list_starred(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """The repos that the authenticated user has starred

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_starred', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_get_stop_watches',
    description='Get list of all existing stopwatches',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_get_stop_watches(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get list of all existing stopwatches

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get_stop_watches', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_current_list_subscriptions',
    description='List repositories watched by the authenticated user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_list_subscriptions(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List repositories watched by the authenticated user

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_subscriptions', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_list_teams',
    description='List all the teams a user belongs to',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_teams(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all the teams a user belongs to

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_teams', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    name='user_current_tracked_times',
    description="List the current user's tracked times",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_current_tracked_times(page: int = 1, limit: int = 50, since: str = "", before: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the current user's tracked times

    Args:
        page: page number of results to return (1-based)
        limit: page size of results
        since: Only show times updated after the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: Only show times updated before the given time. This is a timestamp in RFC 3339 format ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_tracked_times', get_user_token(), **args)
    return {'tracked_times': json_to_toon(data)}

@mcp.tool(
    name='user_search',
    description='Search for users',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_search(q: str = "", uid: int = 0, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for users

    Args:
        q: keyword
        uid: ID of the user to search for
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    if q is not None and q != "": args['q'] = q
    if uid is not None and uid != "": args['uid'] = uid
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_search', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_get',
    description='Get a user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_get(username: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a user

    Args:
        username: username of the user whose data is to be listed
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_list_activity_feeds',
    description="List a user's activity feeds",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_activity_feeds(username: str, only_performed_by: bool = False, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a user's activity feeds

    Args:
        username: username of the user whose activity feeds are to be listed
        only_performed_by: if true, only show actions performed by the requested user
        date: the date of the activities to be found
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if only_performed_by is not None and only_performed_by != "": args['only-performed-by'] = only_performed_by
    if date is not None and date != "": args['date'] = date
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_activity_feeds', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_list_followers',
    description="List the given user's followers",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_followers(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the given user's followers

    Args:
        username: username of the user whose followers are to be listed
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_followers', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_list_following',
    description='List the users that the given user is following',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_following(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the users that the given user is following

    Args:
        username: username of the user whose followed users are to be listed
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_following', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_check_following',
    description='Check if one user is following another user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_check_following(username: str, target: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if one user is following another user

    Args:
        username: username of the following user
        target: username of the followed user
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args['target'] = target
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_check_following', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_list_gpg_keys',
    description="List the given user's GPG keys",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_gpg_keys(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the given user's GPG keys

    Args:
        username: username of the user whose GPG key list is to be obtained
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_gpg_keys', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_get_heatmap_data',
    description="Get a user's heatmap",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_get_heatmap_data(username: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a user's heatmap

    Args:
        username: username of the user whose heatmap is to be obtained
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get_heatmap_data', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_list_keys',
    description="List the given user's public keys",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_keys(username: str, fingerprint: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the given user's public keys

    Args:
        username: username of the user whose public keys are to be listed
        fingerprint: fingerprint of the key
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if fingerprint is not None and fingerprint != "": args['fingerprint'] = fingerprint
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_keys', get_user_token(), **args)
    return {'deploy_keys': json_to_toon(data)}

@mcp.tool(
    name='org_list_user_orgs',
    description="List a user's organizations",
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_list_user_orgs(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a user's organizations

    Args:
        username: username of the user whose organizations are to be listed
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_user_orgs', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    name='org_get_user_permissions',
    description='Get user permissions in organization',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def org_get_user_permissions(username: str, org: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get user permissions in organization

    Args:
        username: username of the user whose permissions are to be obtained
        org: name of the organization
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args['org'] = org
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get_user_permissions', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    name='user_list_repos',
    description='List the repos owned by the given user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_repos(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the repos owned by the given user

    Args:
        username: username of the user whose owned repos are to be listed
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_repos', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_list_starred',
    description='The repos that the given user has starred',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_starred(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """The repos that the given user has starred

    Args:
        username: username of the user whose starred repos are to be listed
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_starred', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='user_list_subscriptions',
    description='List the repositories watched by a user',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def user_list_subscriptions(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the repositories watched by a user

    Args:
        username: username of the user whose watched repos are to be listed
        page: page number of results to return (1-based)
        limit: page size of results
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_subscriptions', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    name='get_version',
    description='Returns the version of the Gitea application',
    tags={"read", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False),
)
async def get_version(include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Returns the version of the Gitea application

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    args: dict[str, Any] = {}
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_version', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data


@mcp.tool(
    name="upload_generic_package",
    description="Upload a text file as a Gitea generic package (text-only helper).",
    tags={"write", "gitea"},
    annotations=ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False),
)
async def upload_generic_package(owner: str, package_name: str, version: str, filename: str,
                                 content: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Upload a text file as a Gitea generic package.

    Args:
        owner: package owner (user or organization)
        package_name: generic package name
        version: package version
        filename: file name stored in the package
        content: text content of the package file
        sudo: Admin-only username to execute this request as (Gitea Sudo header).
        ctx: MCP context (injected).
    """
    return await get_client().upload_generic_package(
        get_user_token(), owner, package_name, version, filename, content, sudo=sudo
    )


def main():
    if not os.getenv("GITEA_BASE_URL"):
        print("ERROR: GITEA_BASE_URL environment variable is required", file=sys.stderr)
        sys.exit(1)
    port_env = os.getenv("MCP_SERVER_PORT")
    if not port_env:
        print("ERROR: MCP_SERVER_PORT environment variable is required", file=sys.stderr)
        sys.exit(1)
    host = "0.0.0.0"
    port = int(port_env)
    path = "/mcp"
    if IS_STATEFUL:
        app = mcp.http_app(path=path, json_response=True)
    else:
        app = mcp.http_app(path=path, json_response=True, stateless_http=True)
    app = AuthMiddleware(app)
    print(f"Starting Gitea MCP server on http://{host}:{port}{path}")
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
