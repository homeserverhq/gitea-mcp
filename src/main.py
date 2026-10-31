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

class CreateLabelOption(BaseModel):
    color: str = Field(..., description='Color.')
    description: str = Field(default='', description="Description provides additional context about the label's purpose.")
    exclusive: bool = Field(default=False, description='Exclusive.')
    is_archived: bool = Field(default=False, description='Is archived.')
    name: str = Field(..., description='Name.')

class CreateOrgOption(BaseModel):
    description: str = Field(default='', description='The description of the organization.')
    email: str = Field(default='', description='The email address of the organization.')
    full_name: str = Field(default='', description='The full display name of the organization.')
    location: str = Field(default='', description='The location of the organization.')
    repo_admin_change_team_access: bool = Field(default=False, description='Whether repository administrators can change team access.')
    username: str = Field(..., description='username of the organization.')
    visibility: Optional[Literal['public', 'limited', 'private']] = Field(default='public', description='possible values are `public` (default), `limited` or `private`.')
    website: str = Field(default='', description='The website URL of the organization.')

class EditBranchProtectionOption(BaseModel):
    approvals_whitelist_teams: Optional[list[str]] = Field(default=None, description='Approvals whitelist teams.')
    approvals_whitelist_username: Optional[list[str]] = Field(default=None, description='Approvals whitelist username.')
    block_admin_merge_override: bool = Field(default=False, description='Block admin merge override.')
    block_on_official_review_requests: bool = Field(default=False, description='Block on official review requests.')
    block_on_outdated_branch: bool = Field(default=False, description='Block on outdated branch.')
    block_on_rejected_reviews: bool = Field(default=False, description='Block on rejected reviews.')
    dismiss_stale_approvals: bool = Field(default=False, description='Dismiss stale approvals.')
    enable_approvals_whitelist: bool = Field(default=False, description='Enable approvals whitelist.')
    enable_force_push: bool = Field(default=False, description='Enable force push.')
    enable_force_push_allowlist: bool = Field(default=False, description='Enable force push allowlist.')
    enable_merge_whitelist: bool = Field(default=False, description='Enable merge whitelist.')
    enable_push: bool = Field(default=False, description='Enable push.')
    enable_push_whitelist: bool = Field(default=False, description='Enable push whitelist.')
    enable_status_check: bool = Field(default=False, description='Enable status check.')
    force_push_allowlist_deploy_keys: bool = Field(default=False, description='Force push allowlist deploy keys.')
    force_push_allowlist_teams: Optional[list[str]] = Field(default=None, description='Force push allowlist teams.')
    force_push_allowlist_usernames: Optional[list[str]] = Field(default=None, description='Force push allowlist usernames.')
    ignore_stale_approvals: bool = Field(default=False, description='Ignore stale approvals.')
    merge_whitelist_teams: Optional[list[str]] = Field(default=None, description='Merge whitelist teams.')
    merge_whitelist_usernames: Optional[list[str]] = Field(default=None, description='Merge whitelist usernames.')
    priority: int = Field(default=0, description='Priority.')
    protected_file_patterns: str = Field(default='', description='Protected file patterns.')
    push_whitelist_deploy_keys: bool = Field(default=False, description='Push whitelist deploy keys.')
    push_whitelist_teams: Optional[list[str]] = Field(default=None, description='Push whitelist teams.')
    push_whitelist_usernames: Optional[list[str]] = Field(default=None, description='Push whitelist usernames.')
    require_signed_commits: bool = Field(default=False, description='Require signed commits.')
    required_approvals: int = Field(default=0, description='Required approvals.')
    status_check_contexts: Optional[list[str]] = Field(default=None, description='Status check contexts.')
    unprotected_file_patterns: str = Field(default='', description='Unprotected file patterns.')

class CreatePullReviewComment(BaseModel):
    body: str = Field(default='', description='Review comment text (e.g. Please add unit tests).')
    new_position: int = Field(default=0, description='Line number in the new file version, or 0 (e.g. 12).')
    old_position: int = Field(default=0, description='Line number in the old file version, or 0 (e.g. 0).')
    path: str = Field(default='', description='File path relative to the repository root (e.g. src/main.py).')

class IssueMeta(BaseModel):
    index: int = Field(default=0, description='Index.')
    owner: str = Field(default='', description="owner of the issue's repo.")
    repo: str = Field(default='', description='Repo.')

class CreateRepoOption(BaseModel):
    auto_init: bool = Field(default=False, description='Whether the repository should be auto-initialized?.')
    default_branch: str = Field(default='', description='DefaultBranch of the repository (used when initializes and in template).')
    description: str = Field(default='', description='Description of the repository to create.')
    gitignores: str = Field(default='', description='Gitignores to use.')
    issue_labels: str = Field(default='', description='Label-Set to use.')
    license: str = Field(default='', description='License to use.')
    name: str = Field(..., description='Name of the repository to create.')
    object_format_name: Optional[Literal['sha1', 'sha256']] = Field(default='sha1', description='ObjectFormatName of the underlying git repository.')
    private: bool = Field(default=False, description='Whether the repository is private.')
    readme: str = Field(default='', description='Readme of the repository to create.')
    template: bool = Field(default=False, description='Whether the repository is template.')
    trust_model: Optional[Literal['default', 'collaborator', 'committer', 'collaboratorcommitter']] = Field(default='default', description='TrustModel of the repository.')

class RenameOrgOption(BaseModel):
    new_name: str = Field(..., description='New username for this org. This name cannot be in use yet by any other user.')

class PullReviewRequestOptions(BaseModel):
    reviewers: Optional[list[str]] = Field(default=None, description='Reviewers.')
    team_reviewers: Optional[list[str]] = Field(default=None, description='Team reviewers.')

class CreateIssueOption(BaseModel):
    assignee: str = Field(default='', description='deprecated.')
    assignees: Optional[list[str]] = Field(default=None, description='Assignees.')
    body: str = Field(default='', description='Body.')
    closed: bool = Field(default=False, description='Closed.')
    due_date: str = Field(default='', description='Due date.')
    labels: Optional[list[int]] = Field(default=None, description='list of label ids.')
    milestone: int = Field(default=0, description='milestone id.')
    ref: str = Field(default='', description='Ref.')
    title: str = Field(..., description='Title.')

class EditDeadlineOption(BaseModel):
    due_date: str = Field(..., description='Due date.')

class DismissPullReviewOptions(BaseModel):
    message: str = Field(default='', description='Message.')
    priors: bool = Field(default=False, description='Priors.')

class GenerateRepoOption(BaseModel):
    avatar: bool = Field(default=False, description='include avatar of the template repo.')
    default_branch: str = Field(default='', description='Default branch of the new repository.')
    description: str = Field(default='', description='Description of the repository to create.')
    git_content: bool = Field(default=False, description='include git content of default branch in template repo.')
    git_hooks: bool = Field(default=False, description='include git hooks in template repo.')
    labels: bool = Field(default=False, description='include labels in template repo.')
    name: str = Field(..., description='Name.')
    owner: str = Field(..., description="the organization's name or individual user's name who will own the new repository.")
    private: bool = Field(default=False, description='Whether the repository is private.')
    protected_branch: bool = Field(default=False, description='include protected branches in template repo.')
    topics: bool = Field(default=False, description='include topics in template repo.')
    webhooks: bool = Field(default=False, description='include webhooks in template repo.')

class AddCollaboratorOption(BaseModel):
    permission: Optional[Literal['read', 'write', 'admin']] = Field(default='read', description='Permission.')

class CreateStatusOption(BaseModel):
    context: str = Field(default='', description='Context is the unique context identifier for the status.')
    description: str = Field(default='', description='Description provides a brief description of the status.')
    state: Optional[Literal['pending', 'success', 'error', 'failure', 'warning', 'skipped']] = Field(default='pending', description='State represents the status state to set (pending, success, error, failure) pending CommitStatusPending  CommitStatusPending is for when the CommitStatus is Pending success CommitStatusSuccess  CommitStatusSuccess is for when the CommitStatus is Success error CommitStatusError  CommitStatusError is for when the CommitStatus is Error failure CommitStatusFailure  CommitStatusFailure is for when the CommitStatus is Failure warning CommitStatusWarning  CommitStatusWarning is for when the CommitStatus is Warning skipped CommitStatusSkipped  CommitStatusSkipped is for when CommitStatus is Skipped.')
    target_url: str = Field(default='', description='TargetURL is the URL to link to for more details.')

class MigrateRepoOptions(BaseModel):
    auth_password: str = Field(default='', description='Auth password.')
    auth_token: str = Field(default='', description='Auth token.')
    auth_username: str = Field(default='', description='Auth username.')
    aws_access_key_id: str = Field(default='', description='Aws access key id.')
    aws_secret_access_key: str = Field(default='', description='Aws secret access key.')
    clone_addr: str = Field(..., description='Clone addr.')
    description: str = Field(default='', description='Description.')
    issues: bool = Field(default=False, description='Issues.')
    labels: bool = Field(default=False, description='Labels.')
    lfs: bool = Field(default=False, description='Lfs.')
    lfs_endpoint: str = Field(default='', description='Lfs endpoint.')
    milestones: bool = Field(default=False, description='Milestones.')
    mirror: bool = Field(default=False, description='Mirror.')
    mirror_interval: str = Field(default='', description='Mirror interval.')
    private: bool = Field(default=False, description='Private.')
    pull_requests: bool = Field(default=False, description='Pull requests.')
    releases: bool = Field(default=False, description='Releases.')
    repo_name: str = Field(..., description='Repo name.')
    repo_owner: str = Field(default='', description="the organization's name or individual user's name who will own the migrated repository.")
    service: Optional[Literal['git', 'github', 'gitea', 'gitlab', 'gogs', 'onedev', 'gitbucket', 'codebase', 'codecommit']] = Field(default='git', description='Service.')
    uid: int = Field(default=0, description='deprecated (only for backwards compatibility, use repo_owner instead).')
    wiki: bool = Field(default=False, description='Wiki.')

class CreateTagProtectionOption(BaseModel):
    name_pattern: str = Field(default='', description='The pattern to match tag names for protection.')
    whitelist_teams: Optional[list[str]] = Field(default=None, description='List of team names allowed to create/delete protected tags.')
    whitelist_usernames: Optional[list[str]] = Field(default=None, description='List of usernames allowed to create/delete protected tags.')

class IssueLabelsOption(BaseModel):
    labels: Optional[list[Any]] = Field(default=None, description='Labels can be a list of integers representing label IDs or a list of strings representing label names.')

class CreateBranchProtectionOption(BaseModel):
    approvals_whitelist_teams: Optional[list[str]] = Field(default=None, description='Approvals whitelist teams.')
    approvals_whitelist_username: Optional[list[str]] = Field(default=None, description='Approvals whitelist username.')
    block_admin_merge_override: bool = Field(default=False, description='Block admin merge override.')
    block_on_official_review_requests: bool = Field(default=False, description='Block on official review requests.')
    block_on_outdated_branch: bool = Field(default=False, description='Block on outdated branch.')
    block_on_rejected_reviews: bool = Field(default=False, description='Block on rejected reviews.')
    branch_name: str = Field(default='', description='Deprecated: true.')
    dismiss_stale_approvals: bool = Field(default=False, description='Dismiss stale approvals.')
    enable_approvals_whitelist: bool = Field(default=False, description='Enable approvals whitelist.')
    enable_force_push: bool = Field(default=False, description='Enable force push.')
    enable_force_push_allowlist: bool = Field(default=False, description='Enable force push allowlist.')
    enable_merge_whitelist: bool = Field(default=False, description='Enable merge whitelist.')
    enable_push: bool = Field(default=False, description='Enable push.')
    enable_push_whitelist: bool = Field(default=False, description='Enable push whitelist.')
    enable_status_check: bool = Field(default=False, description='Enable status check.')
    force_push_allowlist_deploy_keys: bool = Field(default=False, description='Force push allowlist deploy keys.')
    force_push_allowlist_teams: Optional[list[str]] = Field(default=None, description='Force push allowlist teams.')
    force_push_allowlist_usernames: Optional[list[str]] = Field(default=None, description='Force push allowlist usernames.')
    ignore_stale_approvals: bool = Field(default=False, description='Ignore stale approvals.')
    merge_whitelist_teams: Optional[list[str]] = Field(default=None, description='Merge whitelist teams.')
    merge_whitelist_usernames: Optional[list[str]] = Field(default=None, description='Merge whitelist usernames.')
    priority: int = Field(default=0, description='Priority.')
    protected_file_patterns: str = Field(default='', description='Protected file patterns.')
    push_whitelist_deploy_keys: bool = Field(default=False, description='Push whitelist deploy keys.')
    push_whitelist_teams: Optional[list[str]] = Field(default=None, description='Push whitelist teams.')
    push_whitelist_usernames: Optional[list[str]] = Field(default=None, description='Push whitelist usernames.')
    require_signed_commits: bool = Field(default=False, description='Require signed commits.')
    required_approvals: int = Field(default=0, description='Required approvals.')
    rule_name: str = Field(default='', description='Rule name.')
    status_check_contexts: Optional[list[str]] = Field(default=None, description='Status check contexts.')
    unprotected_file_patterns: str = Field(default='', description='Unprotected file patterns.')

class CreateReleaseOption(BaseModel):
    body: str = Field(default='', description='The release notes or description.')
    draft: bool = Field(default=False, description='Whether to create the release as a draft.')
    name: str = Field(default='', description='The display title of the release.')
    prerelease: bool = Field(default=False, description='Whether to mark the release as a prerelease.')
    tag_message: str = Field(default='', description='The message for the git tag.')
    tag_name: str = Field(..., description='Tag name.')
    target_commitish: str = Field(default='', description='The target commitish for the release.')

class EditTeamOption(BaseModel):
    can_create_org_repo: bool = Field(default=False, description='Whether the team can create repositories in the organization.')
    description: str = Field(default='', description='The description of the team.')
    includes_all_repositories: bool = Field(default=False, description='Whether the team has access to all repositories in the organization.')
    name: str = Field(..., description='Name.')
    permission: Optional[Literal['read', 'write', 'admin']] = Field(default='read', description='Permission.')
    units: Optional[list[str]] = Field(default=None, description='Units.')

class RenameBranchRepoOption(BaseModel):
    name: str = Field(..., description='New branch name.')

class CreatePullRequestOption(BaseModel):
    assignee: str = Field(default='', description='The primary assignee username.')
    assignees: Optional[list[str]] = Field(default=None, description='The list of assignee usernames.')
    base: str = Field(default='', description='The base branch for the pull request.')
    body: str = Field(default='', description='The description body of the pull request.')
    due_date: str = Field(default='', description='Due date.')
    head: str = Field(default='', description="The head branch for the pull request, it could be a branch name on the base repository or a form like `<username>:<branch>` which refers to the user's fork repository's branch.")
    labels: Optional[list[int]] = Field(default=None, description='The list of label IDs to assign to the pull request.')
    milestone: int = Field(default=0, description='The milestone ID to assign to the pull request.')
    reviewers: Optional[list[str]] = Field(default=None, description='The list of reviewer usernames.')
    team_reviewers: Optional[list[str]] = Field(default=None, description='The list of team reviewer names.')
    title: str = Field(default='', description='The title of the pull request.')

class CommitDateOptions(BaseModel):
    author: str = Field(default='', description='ISO 8601 format (2026-06-22T15:00:00-04:00).')
    committer: str = Field(default='', description='ISO 8601 format (2026-06-22T15:00:00-04:00).')

class UpdateBranchProtectionPriories(BaseModel):
    ids: Optional[list[int]] = Field(default=None, description='Ids.')

class CreateBranchRepoOption(BaseModel):
    new_branch_name: str = Field(..., description='Name of the branch to create.')
    old_branch_name: str = Field(default='', description='Deprecated: true Name of the old branch to create from.')
    old_ref_name: str = Field(default='', description='Name of the old branch/tag/commit to create from.')

class ExternalTracker(BaseModel):
    external_tracker_format: str = Field(default='', description='External issue tracker URL format using {user}, {repo}, and {index} placeholders (e.g. https://tracker.example.com/{repo}/{index}).')
    external_tracker_regexp_pattern: str = Field(default='', description='Regular expression matching external issue numbers (e.g. \\\\d+).')
    external_tracker_style: str = Field(default='', description='External issue number format: numeric, alphanumeric, or regexp.')
    external_tracker_url: str = Field(default='', description='External issue tracker URL (e.g. https://tracker.example.com).')

class Identity(BaseModel):
    email: str = Field(default='', description='Email address (e.g. jane@example.com).')
    name: str = Field(default='', description="Person's name (e.g. Jane Doe).")

class CreateTeamOption(BaseModel):
    can_create_org_repo: bool = Field(default=False, description='Whether the team can create repositories in the organization.')
    description: str = Field(default='', description='The description of the team.')
    includes_all_repositories: bool = Field(default=False, description='Whether the team has access to all repositories in the organization.')
    name: str = Field(..., description='Name.')
    permission: Optional[Literal['read', 'write', 'admin']] = Field(default='read', description='Permission.')
    units: Optional[list[str]] = Field(default=None, description='Units.')

class EditReactionOption(BaseModel):
    content: str = Field(default='', description='The reaction content (e.g., emoji or reaction type).')

class EditIssueOption(BaseModel):
    assignee: str = Field(default='', description='deprecated.')
    assignees: Optional[list[str]] = Field(default=None, description='Assignees.')
    body: str = Field(default='', description='Body.')
    due_date: str = Field(default='', description='Due date.')
    milestone: int = Field(default=0, description='Milestone.')
    ref: str = Field(default='', description='Ref.')
    state: str = Field(default='', description='State.')
    title: str = Field(default='', description='Title.')
    unset_due_date: bool = Field(default=False, description='Unset due date.')

class LockIssueOption(BaseModel):
    lock_reason: str = Field(default='', description='Lock reason.')

class EditIssueCommentOption(BaseModel):
    body: str = Field(..., description='Body.')

class ApplyDiffPatchFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='Author.')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used.')
    committer: Optional[Identity] = Field(default=None, description='Committer.')
    content: str = Field(..., description='Content.')
    dates: Optional[CommitDateOptions] = Field(default=None, description='Dates.')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used.')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file.')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class CreateMilestoneOption(BaseModel):
    description: str = Field(default='', description='Description provides details about the milestone.')
    due_on: str = Field(default='', description='Due on.')
    state: Optional[Literal['open', 'closed']] = Field(default='open', description='State.')
    title: str = Field(default='', description='Title is the title of the new milestone.')

class ExternalWiki(BaseModel):
    external_wiki_url: str = Field(default='', description='External wiki URL (e.g. https://wiki.example.com).')

class CreateFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='Author.')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used.')
    committer: Optional[Identity] = Field(default=None, description='Committer.')
    content: str = Field(..., description='content must be base64 encoded.')
    dates: Optional[CommitDateOptions] = Field(default=None, description='Dates.')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used.')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file.')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class MergeUpstreamRequest(BaseModel):
    branch: str = Field(default='', description='Branch.')
    ff_only: bool = Field(default=False, description='Ff only.')

class EditReleaseOption(BaseModel):
    body: str = Field(default='', description='The new release notes or description.')
    draft: bool = Field(default=False, description='Whether to change the draft status.')
    name: str = Field(default='', description='The new display title of the release.')
    prerelease: bool = Field(default=False, description='Whether to change the prerelease status.')
    tag_name: str = Field(default='', description='The new name of the git tag.')
    target_commitish: str = Field(default='', description='The new target commitish for the release.')

class ChangeFileOperation(BaseModel):
    content: str = Field(default='', description='Plain-text file content.')
    from_path: str = Field(default='', description='Original file path for a rename or move (e.g. old.txt).')
    operation: Literal['create', 'update', 'upload', 'rename', 'delete'] = Field(..., description='File operation: create, update, upload, rename, or delete.')
    path: str = Field(..., description='File path relative to the repository root (e.g. docs/README.md).')
    sha: str = Field(default='', description='Blob SHA for an existing file (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).')

class AddTimeOption(BaseModel):
    created: str = Field(default='', description='Created.')
    time: int = Field(..., description='time in seconds.')
    user_name: str = Field(default='', description='username of the user who spent the time working on the issue (optional).')

class CreateIssueCommentOption(BaseModel):
    body: str = Field(..., description='Body.')

class InternalTracker(BaseModel):
    allow_only_contributors_to_track_time: bool = Field(default=False, description='Only allow contributors to track time: true or false (Default: false).')
    enable_issue_dependencies: bool = Field(default=False, description='Enable issue dependencies: true or false (Default: false).')
    enable_time_tracker: bool = Field(default=False, description='Enable time tracking: true or false (Default: false).')

class EditTagProtectionOption(BaseModel):
    name_pattern: str = Field(default='', description='The pattern to match tag names for protection.')
    whitelist_teams: Optional[list[str]] = Field(default=None, description='List of team names allowed to create/delete protected tags.')
    whitelist_usernames: Optional[list[str]] = Field(default=None, description='List of usernames allowed to create/delete protected tags.')

class CreateTagOption(BaseModel):
    message: str = Field(default='', description='The message to associate with the tag.')
    tag_name: str = Field(..., description='Tag name.')
    target: str = Field(default='', description='The target commit SHA or branch name for the tag.')

class EditOrgOption(BaseModel):
    description: str = Field(default='', description='The description of the organization.')
    email: str = Field(default='', description='The email address of the organization.')
    full_name: str = Field(default='', description='The full display name of the organization.')
    location: str = Field(default='', description='The location of the organization.')
    repo_admin_change_team_access: bool = Field(default=False, description='Whether repository administrators can change team access.')
    visibility: Optional[Literal['public', 'limited', 'private']] = Field(default='public', description='possible values are `public`, `limited` or `private`.')
    website: str = Field(default='', description='The website URL of the organization.')

class RepoTopicOptions(BaseModel):
    topics: Optional[list[str]] = Field(default=None, description='list of topic names.')

class EditLabelOption(BaseModel):
    color: str = Field(default='', description='Color.')
    description: str = Field(default='', description="Description provides additional context about the label's purpose.")
    exclusive: bool = Field(default=False, description='Exclusive.')
    is_archived: bool = Field(default=False, description='Is archived.')
    name: str = Field(default='', description='Name is the new display name for the label.')

class CreateKeyOption(BaseModel):
    key: str = Field(..., description='An armored SSH key to add.')
    read_only: bool = Field(default=False, description='Describe if the key has only read access or read/write.')
    title: str = Field(..., description='Title of the key to add.')

class EditMilestoneOption(BaseModel):
    description: str = Field(default='', description='Description provides updated details about the milestone.')
    due_on: str = Field(default='', description='Deadline is the updated due date for the milestone.')
    state: str = Field(default='', description='State indicates the updated state of the milestone.')
    title: str = Field(default='', description='Title is the updated title of the milestone.')

class CreateForkOption(BaseModel):
    name: str = Field(default='', description='name of the forked repository.')
    organization: str = Field(default='', description='organization name, if forking into an organization.')

class EditPullRequestOption(BaseModel):
    allow_maintainer_edit: bool = Field(default=False, description='Whether to allow maintainer edits.')
    assignee: str = Field(default='', description='The new primary assignee username.')
    assignees: Optional[list[str]] = Field(default=None, description='The new list of assignee usernames.')
    base: str = Field(default='', description='The new base branch for the pull request.')
    body: str = Field(default='', description='The new description body for the pull request.')
    due_date: str = Field(default='', description='Due date.')
    labels: Optional[list[int]] = Field(default=None, description='The new list of label IDs for the pull request.')
    milestone: int = Field(default=0, description='The new milestone ID for the pull request.')
    state: str = Field(default='', description='The new state for the pull request.')
    title: str = Field(default='', description='The new title for the pull request.')
    unset_due_date: bool = Field(default=False, description='Whether to remove the current deadline.')

class MergePullRequestOption(BaseModel):
    Do: Literal['merge', 'rebase', 'rebase-merge', 'squash', 'fast-forward-only', 'manually-merged'] = Field(..., description='Do.')
    MergeCommitID: str = Field(default='', description='Mergecommitid.')
    MergeMessageField: str = Field(default='', description='Mergemessagefield.')
    MergeTitleField: str = Field(default='', description='Mergetitlefield.')
    delete_branch_after_merge: bool = Field(default=False, description='Delete branch after merge.')
    force_merge: bool = Field(default=False, description='Force merge.')
    head_commit_id: str = Field(default='', description='Head commit id.')
    merge_when_checks_succeed: bool = Field(default=False, description='Merge when checks succeed.')

class CreateWikiPageOptions(BaseModel):
    content_base64: str = Field(default='', description='content must be base64 encoded.')
    message: str = Field(default='', description='optional commit message summarizing the change.')
    title: str = Field(default='', description='page title. leave empty to keep unchanged.')

class UpdateFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='Author.')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used.')
    committer: Optional[Identity] = Field(default=None, description='Committer.')
    content: str = Field(..., description='content must be base64 encoded.')
    dates: Optional[CommitDateOptions] = Field(default=None, description='Dates.')
    from_path: str = Field(default='', description='from_path (optional) is the path of the original file which will be moved/renamed to the path in the URL.')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used.')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file.')
    sha: str = Field(..., description='the blob ID (SHA) for the file that already exists, it is required for changing existing files.')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

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
    default_allow_maintainer_edit: bool = Field(default=False, description='set to `true` to allow edits from maintainers by default.')
    default_branch: str = Field(default='', description='sets the default branch for this repository.')
    default_delete_branch_after_merge: bool = Field(default=False, description='set to `true` to delete pr branch after merge by default.')
    default_merge_style: str = Field(default='', description='set to a merge style to be used by this repository: "merge", "rebase", "rebase-merge", "squash", or "fast-forward-only".')
    description: str = Field(default='', description='a short description of the repository.')
    enable_prune: bool = Field(default=False, description='enable prune - remove obsolete remote-tracking references when mirroring.')
    external_tracker: Optional[ExternalTracker] = Field(default=None, description='External tracker.')
    external_wiki: Optional[ExternalWiki] = Field(default=None, description='External wiki.')
    has_actions: bool = Field(default=False, description='either `true` to enable actions unit, or `false` to disable them.')
    has_code: bool = Field(default=False, description='either `true` to enable code for this repository or `false` to disable it.')
    has_issues: bool = Field(default=False, description='either `true` to enable issues for this repository or `false` to disable them.')
    has_packages: bool = Field(default=False, description='either `true` to enable packages unit, or `false` to disable them.')
    has_projects: bool = Field(default=False, description='either `true` to enable project unit, or `false` to disable them.')
    has_pull_requests: bool = Field(default=False, description='either `true` to allow pull requests, or `false` to prevent pull request.')
    has_releases: bool = Field(default=False, description='either `true` to enable releases unit, or `false` to disable them.')
    has_wiki: bool = Field(default=False, description='either `true` to enable the wiki for this repository or `false` to disable it.')
    ignore_whitespace_conflicts: bool = Field(default=False, description='either `true` to ignore whitespace for conflicts, or `false` to not ignore whitespace.')
    internal_tracker: Optional[InternalTracker] = Field(default=None, description='Internal tracker.')
    mirror_interval: str = Field(default='', description='set to a string like `8h30m0s` to set the mirror interval time.')
    name: str = Field(default='', description='name of the repository.')
    private: bool = Field(default=False, description='either `true` to make the repository private or `false` to make it public. Note: you will get a 422 error if the organization restricts changing repository visibility to organization owners and a non-owner tries to change the value of private.')
    projects_mode: str = Field(default='', description='`repo` to only allow repo-level projects, `owner` to only allow owner projects, `all` to allow both.')
    template: bool = Field(default=False, description='either `true` to make this repository a template or `false` to make it a normal repository.')
    website: str = Field(default='', description='a URL with more information about the repository.')

class DeleteFileOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='Author.')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used.')
    committer: Optional[Identity] = Field(default=None, description='Committer.')
    dates: Optional[CommitDateOptions] = Field(default=None, description='Dates.')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used.')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file.')
    sha: str = Field(..., description='the blob ID (SHA) for the file that already exists, it is required for changing existing files.')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class ChangeFilesOptions(BaseModel):
    author: Optional[Identity] = Field(default=None, description='Author.')
    branch: str = Field(default='', description='branch (optional) to base this file from. if not given, the default branch is used.')
    committer: Optional[Identity] = Field(default=None, description='Committer.')
    dates: Optional[CommitDateOptions] = Field(default=None, description='Dates.')
    files: list[ChangeFileOperation] = Field(..., description='list of file operations.')
    message: str = Field(default='', description='message (optional) for the commit of this file. if not supplied, a default message will be used.')
    new_branch: str = Field(default='', description='new_branch (optional) will make a new branch from `branch` before creating the file.')
    signoff: bool = Field(default=False, description='Add a Signed-off-by trailer by the committer at the end of the commit log message.')

class CreatePullReviewOptions(BaseModel):
    body: str = Field(default='', description='Body.')
    comments: Optional[list[CreatePullReviewComment]] = Field(default=None, description='Comments.')
    commit_id: str = Field(default='', description='Commit id.')
    event: str = Field(default=None, description='Event.')

class SubmitPullReviewOptions(BaseModel):
    body: str = Field(default='', description='Body.')
    event: str = Field(default=None, description='Event.')


# =============================================================================
# Tools
# =============================================================================

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Notify Get List", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_get_list(all: bool = False, status_types: list[str] | None = None, subject_type: list[Literal['issue', 'pull', 'commit', 'repository']] | None = None, since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List users's notification threads.

    Args:
        all: Whether to include all items: true or false.
        status_types: Notification status types. Options: unread, read, or pinned.
        subject_type: Notification subject types. Options: issue, pull, commit, or repository.
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status_types'] = status_types
    if subject_type is not None and subject_type != "": args['subject_type'] = subject_type
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_get_list', get_user_token(), **args)
    return {'notifications': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Notify Read List", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_read_list(last_read_at: str = "", all: str = "", status_types: list[str] | None = None, to_status: str = "", sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Mark notification threads as read, pinned or unread.

    Args:
        last_read_at: ISO 8601 format (2026-06-22T15:00:00-04:00).
        all: Whether to include all items: true or false.
        status_types: Notification status types. Options: unread, read, or pinned.
        to_status: Target notification status. Options: read, unread, or pinned.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if last_read_at is not None and last_read_at != "": args['last_read_at'] = last_read_at
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status_types'] = status_types
    if to_status is not None and to_status != "": args['to_status'] = to_status
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_read_list', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Notify New Available", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_new_available(include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if unread notifications exist.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_new_available', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Notify Get Thread", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_get_thread(id: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get notification thread by ID.

    Args:
        id: Resource ID.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_get_thread', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Notify Read Thread", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_read_thread(id: str, to_status: str = 'read', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Mark notification thread as read by ID.

    Args:
        id: Resource ID.
        to_status: Target notification status. Options: read, unread, or pinned.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if to_status is not None and to_status != "": args['to_status'] = to_status
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_read_thread', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Create Org Repo Deprecated", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_org_repo_deprecated(org: str, description: str, name: str, auto_init: bool = False, default_branch: str = '', gitignores: str = '', issue_labels: str = '', license: str = '', object_format_name: Literal['sha1', 'sha256'] = 'sha1', private: bool = False, readme: str = '', template: bool = False, trust_model: Literal['default', 'collaborator', 'committer', 'collaboratorcommitter'] = 'default', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository in an organization.

    Args:
        org: Organization name (e.g. acme).
        auto_init: Whether to initialize the repository: true or false.
        default_branch: Default branch name (e.g. main).
        description: Description text (e.g. Short description).
        gitignores: Gitignore template name.
        issue_labels: Issue label template name.
        license: License template name.
        name: Resource name (e.g. my-resource).
        object_format_name: Git object format. Options: sha1 or sha256.
        private: Whether the repository is private: true or false.
        readme: Readme template name.
        template: Whether the repository is a template: true or false.
        trust_model: Repository trust model. Options: default, collaborator, committer, or collaboratorcommitter.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    if object_format_name is not None and object_format_name != 'sha1': args['object_format_name'] = object_format_name
    if private: args['private'] = private
    if readme != "": args['readme'] = readme
    if template: args['template'] = template
    if trust_model is not None and trust_model != 'default': args['trust_model'] = trust_model
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_org_repo_deprecated', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Org Get All", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_get_all(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get list of organizations.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get_all', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Create", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def org_create(description: str, username: str, email: str = '', full_name: str = '', location: str = '', repo_admin_change_team_access: bool = False, visibility: Literal['public', 'limited', 'private'] = 'public', website: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create an organization.

    Args:
        description: Description text (e.g. Short description).
        email: Email address (e.g. jane@example.com).
        full_name: Full display name (e.g. Jane Doe).
        location: Location (e.g. Berlin).
        repo_admin_change_team_access: Whether repo admins may change team access: true or false.
        username: Username (e.g. amanda).
        visibility: Organization visibility. Options: public, limited, or private.
        website: Website URL (e.g. https://example.com).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['description'] = description
    if email != "": args['email'] = email
    if full_name != "": args['full_name'] = full_name
    if location != "": args['location'] = location
    if repo_admin_change_team_access: args['repo_admin_change_team_access'] = repo_admin_change_team_access
    args['username'] = username
    if visibility is not None and visibility != 'public': args['visibility'] = visibility
    if website != "": args['website'] = website
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_create', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Delete", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_delete(org: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete an organization.

    Args:
        org: Organization name (e.g. acme).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Org Get", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_get(org: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get an organization.

    Args:
        org: Organization name (e.g. acme).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Edit", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_edit(org: str, description: str = '', email: str = '', full_name: str = '', location: str = '', repo_admin_change_team_access: bool = False, visibility: Literal['public', 'limited', 'private'] = 'public', website: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit an organization.

    Args:
        org: Organization name (e.g. acme).
        description: Description text (e.g. Short description).
        email: Email address (e.g. jane@example.com).
        full_name: Full display name (e.g. Jane Doe).
        location: Location (e.g. Berlin).
        repo_admin_change_team_access: Whether repo admins may change team access: true or false.
        visibility: Organization visibility. Options: public, limited, or private.
        website: Website URL (e.g. https://example.com).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    if description != "": args['description'] = description
    if email != "": args['email'] = email
    if full_name != "": args['full_name'] = full_name
    if location != "": args['location'] = location
    if repo_admin_change_team_access: args['repo_admin_change_team_access'] = repo_admin_change_team_access
    if visibility is not None and visibility != 'public': args['visibility'] = visibility
    if website != "": args['website'] = website
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_edit', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Org List Activity Feeds", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_activity_feeds(org: str, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's activity feeds.

    Args:
        org: Organization name (e.g. acme).
        date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Labels", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_labels(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's labels.

    Args:
        org: Organization name (e.g. acme).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Create Label", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def org_create_label(org: str, color: str, description: str, name: str, exclusive: bool = False, is_archived: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a label for an organization.

    Args:
        org: Organization name (e.g. acme).
        color: Hex color code (e.g. #d73a4a).
        description: Description text (e.g. Short description).
        exclusive: Whether the label is exclusive: true or false.
        is_archived: Whether the label is archived: true or false.
        name: Resource name (e.g. my-resource).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Delete Label", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_delete_label(org: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a label.

    Args:
        org: Organization name (e.g. acme).
        id: Label ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete_label', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Get Label", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_get_label(org: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a single label.

    Args:
        org: Organization name (e.g. acme).
        id: Label ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Edit Label", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_edit_label(org: str, id: int, color: str = '', description: str = '', exclusive: bool = False, is_archived: bool = False, name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a label.

    Args:
        org: Organization name (e.g. acme).
        id: Label ID (e.g. 1).
        color: Hex color code (e.g. #d73a4a).
        description: Description text (e.g. Short description).
        exclusive: Whether the label is exclusive: true or false.
        is_archived: Whether the label is archived: true or false.
        name: Resource name (e.g. my-resource).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Members", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_members(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's members.

    Args:
        org: Organization name (e.g. acme).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Delete Member", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_delete_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a member from an organization.

    Args:
        org: Organization name (e.g. acme).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Is Member", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_is_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a user is a member of an organization.

    Args:
        org: Organization name (e.g. acme).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_is_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Org List Public Members", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_public_members(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's public members.

    Args:
        org: Organization name (e.g. acme).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Org Conceal Member", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_conceal_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Conceal a user's membership.

    Args:
        org: Organization name (e.g. acme).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_conceal_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Org Is Public Member", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_is_public_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a user is a public member of an organization.

    Args:
        org: Organization name (e.g. acme).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_is_public_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Org Publicize Member", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_publicize_member(org: str, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Publicize a user's membership.

    Args:
        org: Organization name (e.g. acme).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_publicize_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Rename Org", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def rename_org(org: str, new_name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Rename an organization.

    Args:
        org: Organization name (e.g. acme).
        new_name: New username for this org. This name cannot be in use yet by any other user.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['org'] = org
    args['new_name'] = new_name
    if sudo: args["sudo"] = sudo
    data = await get_client().call('rename_org', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Repos", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_repos(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's repos.

    Args:
        org: Organization name (e.g. acme).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Create Org Repo", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_org_repo(org: str, description: str, name: str, auto_init: bool = False, default_branch: str = '', gitignores: str = '', issue_labels: str = '', license: str = '', object_format_name: Literal['sha1', 'sha256'] = 'sha1', private: bool = False, readme: str = '', template: bool = False, trust_model: Literal['default', 'collaborator', 'committer', 'collaboratorcommitter'] = 'default', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository in an organization.

    Args:
        org: Organization name (e.g. acme).
        auto_init: Whether to initialize the repository: true or false.
        default_branch: Default branch name (e.g. main).
        description: Description text (e.g. Short description).
        gitignores: Gitignore template name.
        issue_labels: Issue label template name.
        license: License template name.
        name: Resource name (e.g. my-resource).
        object_format_name: Git object format. Options: sha1 or sha256.
        private: Whether the repository is private: true or false.
        readme: Readme template name.
        template: Whether the repository is a template: true or false.
        trust_model: Repository trust model. Options: default, collaborator, committer, or collaboratorcommitter.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    if object_format_name is not None and object_format_name != 'sha1': args['object_format_name'] = object_format_name
    if private: args['private'] = private
    if readme != "": args['readme'] = readme
    if template: args['template'] = template
    if trust_model is not None and trust_model != 'default': args['trust_model'] = trust_model
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_org_repo', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Teams", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_teams(org: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an organization's teams.

    Args:
        org: Organization name (e.g. acme).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Create Team", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def org_create_team(org: str, description: str, name: str, permission: Literal['read', 'write', 'admin'], can_create_org_repo: bool = False, includes_all_repositories: bool = False, units: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a team.

    Args:
        org: Organization name (e.g. acme).
        can_create_org_repo: Whether the team may create organization repositories: true or false.
        description: Description text (e.g. Short description).
        includes_all_repositories: Whether the team includes all repositories: true or false.
        name: Resource name (e.g. my-resource).
        permission: Permission level. Options: read, write, or admin.
        units: Repository units granted to the team. Options: repo.code, repo.issues, repo.ext_issues, repo.pulls, repo.releases, repo.wiki, repo.ext_wiki, repo.projects, repo.packages, or repo.actions.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Team Search", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def team_search(org: str, q: str = "", include_desc: bool = False, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for teams within an organization.

    Args:
        org: Organization name (e.g. acme).
        q: Search query.
        include_desc: include search within team description (defaults to true). true or false.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="List Packages", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def list_packages(owner: str, page: int = 1, limit: int = 50, type: Literal['alpine', 'cargo', 'chef', 'composer', 'conan', 'conda', 'container', 'cran', 'debian', 'generic', 'go', 'helm', 'maven', 'npm', 'nuget', 'pub', 'pypi', 'rpm', 'rubygems', 'swift', 'vagrant'] = 'alpine', q: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets all packages of an owner.

    Args:
        owner: Repository owner username (e.g. solo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        q: Search query.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="List Package Versions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def list_package_versions(owner: str, type: str, name: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets all versions of a package.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Get Latest Package Version", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_latest_package_version(owner: str, type: str, name: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the latest version of a package.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Link Package", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def link_package(owner: str, type: str, name: str, repo_name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Link a package to a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        repo_name: Repository name.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Unlink Package", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def unlink_package(owner: str, type: str, name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unlink a package from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Delete Package", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def delete_package(owner: str, type: str, name: str, version: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a package.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        version: Package version.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Get Package", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_package(owner: str, type: str, name: str, version: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets a package.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        version: Package version.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="List Package Files", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def list_package_files(owner: str, type: str, name: str, version: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets all files of a package.

    Args:
        owner: Repository owner username (e.g. solo).
        type: Resource type. Options: alpine, cargo, chef, composer, conan, conda, container, cran, debian, generic, go, helm, maven, npm, nuget, pub, pypi, rpm, rubygems, swift, or vagrant.
        name: Resource name (e.g. my-resource).
        version: Package version.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue Search Issues", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_search_issues(state: Literal['open', 'closed', 'all'] = 'open', labels: list[str] | None = None, milestones: list[str] | None = None, q: str = "", priority_repo_id: int = 0, type: Literal['issues', 'pulls'] = 'issues', since: str = "", before: str = "", assigned: bool = False, created: bool = False, mentioned: bool = False, review_requested: bool = False, reviewed: bool = False, owner: str = "", team: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for issues across the repositories that the user has access to.

    Args:
        state: State filter. Options: open, closed, or all.
        labels: Label names to filter by (e.g. ["bug", "ui"]).
        milestones: Milestone names or IDs to filter by (e.g. ["v1.0"]).
        q: Search query.
        priority_repo_id: Repository ID to prioritize in the results (e.g. 1).
        type: Issue type: issues or pulls.
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        assigned: Filter issues or pulls assigned to the authenticated user. true or false.
        created: Only show items created by the authenticated user: true or false.
        mentioned: Filter issues or pulls mentioning the authenticated user. true or false.
        review_requested: Filter pull requests where the authenticated user's review was requested. true or false.
        reviewed: Filter pull requests reviewed by the authenticated user. true or false.
        owner: Repository owner username (e.g. solo).
        team: Team name (e.g. developers).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Migrate", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True)
)
async def repo_migrate(clone_addr: str, description: str, repo_name: str, auth_password: str = '', auth_token: str = '', auth_username: str = '', aws_access_key_id: str = '', aws_secret_access_key: str = '', issues: bool = False, labels: bool = False, lfs: bool = False, lfs_endpoint: str = '', milestones: bool = False, mirror: bool = False, mirror_interval: str = '', private: bool = False, pull_requests: bool = False, releases: bool = False, repo_owner: str = '', service: Literal['git', 'github', 'gitea', 'gitlab', 'gogs', 'onedev', 'gitbucket', 'codebase', 'codecommit'] = 'git', uid: int = 0, wiki: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Migrate a remote git repository.

    Args:
        auth_password: Source authentication password.
        auth_token: Source authentication token.
        auth_username: Source authentication username.
        aws_access_key_id: AWS access key ID.
        aws_secret_access_key: AWS secret access key.
        clone_addr: Source repository clone URL.
        description: Description text (e.g. Short description).
        issues: Whether to migrate issues: true or false.
        labels: List of label IDs (e.g. [1, 2]). true or false.
        lfs: Whether to migrate LFS objects: true or false.
        lfs_endpoint: LFS endpoint URL.
        milestones: Milestones. true or false.
        mirror: Whether the repository is a mirror: true or false.
        mirror_interval: Mirror sync interval (e.g. 10m).
        private: Whether the repository is private: true or false.
        pull_requests: Whether to migrate pull requests: true or false.
        releases: Whether to migrate releases: true or false.
        repo_name: Repository name.
        repo_owner: Repository owner username.
        service: Migration service type. Options: git, github, gitea, gitlab, gogs, onedev, gitbucket, codebase, or codecommit.
        uid: User ID (e.g. 1).
        wiki: Whether to migrate wiki pages: true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    if service is not None and service != 'git': args['service'] = service
    if uid != 0: args['uid'] = uid
    if wiki: args['wiki'] = wiki
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_migrate', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Search", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_search(q: str = "", topic_only: bool = False, include_description: bool = False, user_id: int = 0, priority_owner_id: int = 0, team_id: int = 0, starred_by_user_id: int = 0, include_private: bool = False, only_private: bool = False, include_templates: bool = False, only_archived: bool = False, mode: str = "", owned_only: bool = False, sort: str = "", order: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for repositories.

    Args:
        q: Search query.
        topic_only: Only search repositories whose topic matches the query: true or false.
        include_description: Whether to search repository descriptions: true or false.
        user_id: User ID (e.g. 1).
        priority_owner_id: Owner ID to prioritize in results (e.g. 1).
        team_id: Team ID (e.g. 1).
        starred_by_user_id: Only include repositories starred by this user ID (e.g. 1).
        include_private: Include private repositories: true or false.
        only_private: Only include private repositories: true or false.
        include_templates: Include template repositories: true or false.
        only_archived: Only include archived repositories: true or false.
        mode: Repository search mode. Options: fork, source, mirror, or collaborative.
        owned_only: Only include repositories owned by the user: true or false.
        sort: Sort field. Options: alpha, created, updated, size, git_size, lfs_size, stars, forks, or id.
        order: Sort direction. Options: asc or desc.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if q is not None and q != "": args['q'] = q
    if topic_only is not None and topic_only != "": args['topic_only'] = topic_only
    if include_description is not None and include_description != "": args['include_description'] = include_description
    if user_id is not None and user_id != "": args['user_id'] = user_id
    if priority_owner_id is not None and priority_owner_id != "": args['priority_owner_id'] = priority_owner_id
    if team_id is not None and team_id != "": args['team_id'] = team_id
    if starred_by_user_id is not None and starred_by_user_id != "": args['starred_by_user_id'] = starred_by_user_id
    if include_private is not None and include_private != "": args['include_private'] = include_private
    if only_private is not None and only_private != "": args['only_private'] = only_private
    if include_templates is not None and include_templates != "": args['include_templates'] = include_templates
    if only_archived is not None and only_archived != "": args['only_archived'] = only_archived
    if mode is not None and mode != "": args['mode'] = mode
    if owned_only is not None and owned_only != "": args['owned_only'] = owned_only
    if sort is not None and sort != "": args['sort'] = sort
    if order is not None and order != "": args['order'] = order
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_search', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete(owner: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_delete', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Edit", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_edit(owner: str, repo: str, allow_fast_forward_only_merge: bool = False, allow_manual_merge: bool = False, allow_merge_commits: bool = False, allow_rebase: bool = False, allow_rebase_explicit: bool = False, allow_rebase_update: bool = False, allow_squash_merge: bool = False, archived: bool = False, autodetect_manual_merge: bool = False, default_allow_maintainer_edit: bool = False, default_branch: str = '', default_delete_branch_after_merge: bool = False, default_merge_style: str = '', description: str = '', enable_prune: bool = False, external_tracker: ExternalTracker = None, external_wiki: ExternalWiki = None, has_actions: bool = False, has_code: bool = False, has_issues: bool = False, has_packages: bool = False, has_projects: bool = False, has_pull_requests: bool = False, has_releases: bool = False, has_wiki: bool = False, ignore_whitespace_conflicts: bool = False, internal_tracker: InternalTracker = None, mirror_interval: str = '', name: str = '', private: bool = False, projects_mode: str = '', template: bool = False, website: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a repository's properties.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        allow_fast_forward_only_merge: either `true` to allow fast-forward-only merging pull requests, or `false` to prevent fast-forward-only merging. true or false.
        allow_manual_merge: either `true` to allow mark pr as merged manually, or `false` to prevent it. true or false.
        allow_merge_commits: either `true` to allow merging pull requests with a merge commit, or `false` to prevent merging pull requests with merge commits. true or false.
        allow_rebase: either `true` to allow rebase-merging pull requests, or `false` to prevent rebase-merging. true or false.
        allow_rebase_explicit: either `true` to allow rebase with explicit merge commits (--no-ff), or `false` to prevent rebase with explicit merge commits. true or false.
        allow_rebase_update: either `true` to allow updating pull request branch by rebase, or `false` to prevent it. true or false.
        allow_squash_merge: either `true` to allow squash-merging pull requests, or `false` to prevent squash-merging. true or false.
        archived: Whether the repository is archived: true or false.
        autodetect_manual_merge: either `true` to enable AutodetectManualMerge, or `false` to prevent it. Note: In some special cases, misjudgments can occur. true or false.
        default_allow_maintainer_edit: set to `true` to allow edits from maintainers by default. true or false.
        default_branch: Default branch name (e.g. main).
        default_delete_branch_after_merge: set to `true` to delete pr branch after merge by default. true or false.
        default_merge_style: set to a merge style to be used by this repository: "merge", "rebase", "rebase-merge", "squash", or "fast-forward-only".
        description: Description text (e.g. Short description).
        enable_prune: enable prune - remove obsolete remote-tracking references when mirroring. true or false.
        external_tracker: External tracker.
        external_wiki: External wiki.
        has_actions: either `true` to enable actions unit, or `false` to disable them. true or false.
        has_code: either `true` to enable code for this repository or `false` to disable it. true or false.
        has_issues: either `true` to enable issues for this repository or `false` to disable them. true or false.
        has_packages: either `true` to enable packages unit, or `false` to disable them. true or false.
        has_projects: either `true` to enable project unit, or `false` to disable them. true or false.
        has_pull_requests: either `true` to allow pull requests, or `false` to prevent pull request. true or false.
        has_releases: either `true` to enable releases unit, or `false` to disable them. true or false.
        has_wiki: either `true` to enable the wiki for this repository or `false` to disable it. true or false.
        ignore_whitespace_conflicts: either `true` to ignore whitespace for conflicts, or `false` to not ignore whitespace. true or false.
        internal_tracker: Internal tracker.
        mirror_interval: Mirror sync interval (e.g. 10m).
        name: Resource name (e.g. my-resource).
        private: Whether the repository is private: true or false.
        projects_mode: `repo` to only allow repo-level projects, `owner` to only allow owner projects, `all` to allow both.
        template: Whether the repository is a template: true or false.
        website: Website URL (e.g. https://example.com).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Activity Feeds", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_activity_feeds(owner: str, repo: str, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's activity feeds.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Assignees", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_assignees(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Return all users that have write access and can be assigned to issues.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_assignees', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Branch Protection", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_branch_protection(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List branch protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_branch_protection', get_user_token(), **args)
    return {'branch_protections': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Create Branch Protection", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_branch_protection(owner: str, repo: str, branch_name: str, approvals_whitelist_teams: list[str] | None = None, approvals_whitelist_usernames: list[str] | None = None, block_admin_merge_override: bool = False, block_on_official_review_requests: bool = False, block_on_outdated_branch: bool = False, block_on_rejected_reviews: bool = False, dismiss_stale_approvals: bool = False, enable_approvals_whitelist: bool = False, enable_force_push: bool = False, enable_force_push_allowlist: bool = False, enable_merge_whitelist: bool = False, enable_push: bool = False, enable_push_whitelist: bool = False, enable_status_check: bool = False, force_push_allowlist_deploy_keys: bool = False, force_push_allowlist_teams: list[str] | None = None, force_push_allowlist_usernames: list[str] | None = None, ignore_stale_approvals: bool = False, merge_whitelist_teams: list[str] | None = None, merge_whitelist_usernames: list[str] | None = None, priority: int = 0, protected_file_patterns: list[str] | None = None, push_whitelist_deploy_keys: bool = False, push_whitelist_teams: list[str] | None = None, push_whitelist_usernames: list[str] | None = None, require_signed_commits: bool = False, required_approvals: int = 0, rule_name: str = '', status_check_contexts: list[str] | None = None, unprotected_file_patterns: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a branch protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        approvals_whitelist_teams: Team names whose approvals count (e.g. ["value"]).
        approvals_whitelist_usernames: Usernames whose approvals count (e.g. ["value"]).
        block_admin_merge_override: Whether to block admin merge override: true or false.
        block_on_official_review_requests: Whether to block on official review requests: true or false.
        block_on_outdated_branch: Whether to block merging on an outdated branch: true or false.
        block_on_rejected_reviews: Whether to block merging on rejected reviews: true or false.
        branch_name: Branch name to protect.
        dismiss_stale_approvals: Whether to dismiss stale approvals: true or false.
        enable_approvals_whitelist: Whether to enable the approvals whitelist: true or false.
        enable_force_push: Whether to enable force pushes: true or false.
        enable_force_push_allowlist: Whether to enable the force-push allowlist: true or false.
        enable_merge_whitelist: Whether to enable the merge whitelist: true or false.
        enable_push: Whether to enable pushing: true or false.
        enable_push_whitelist: Whether to enable the push whitelist: true or false.
        enable_status_check: Whether to require status checks: true or false.
        force_push_allowlist_deploy_keys: Whether to allow force-push deploy keys: true or false.
        force_push_allowlist_teams: Team names allowed to force-push (e.g. ["value"]).
        force_push_allowlist_usernames: Usernames allowed to force-push (e.g. ["value"]).
        ignore_stale_approvals: Whether to ignore stale approvals: true or false.
        merge_whitelist_teams: Team names allowed to merge (e.g. ["value"]).
        merge_whitelist_usernames: Usernames allowed to merge (e.g. ["value"]).
        priority: Priority value (e.g. 1).
        protected_file_patterns: Protected file patterns (e.g. ["*.md", "docs/*"]).
        push_whitelist_deploy_keys: Whether to allow push deploy keys: true or false.
        push_whitelist_teams: Team names allowed to push (e.g. ["value"]).
        push_whitelist_usernames: Usernames allowed to push (e.g. ["value"]).
        require_signed_commits: Whether to require signed commits: true or false.
        required_approvals: Number of required approvals (e.g. 1).
        rule_name: Branch protection rule name.
        status_check_contexts: Required status check contexts (e.g. ["ci/build"]).
        unprotected_file_patterns: Unprotected file patterns (e.g. ["*.txt"]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if approvals_whitelist_teams is not None: args['approvals_whitelist_teams'] = approvals_whitelist_teams
    if approvals_whitelist_usernames is not None: args['approvals_whitelist_usernames'] = approvals_whitelist_usernames
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
    if protected_file_patterns is not None: args['protected_file_patterns'] = protected_file_patterns
    if push_whitelist_deploy_keys: args['push_whitelist_deploy_keys'] = push_whitelist_deploy_keys
    if push_whitelist_teams is not None: args['push_whitelist_teams'] = push_whitelist_teams
    if push_whitelist_usernames is not None: args['push_whitelist_usernames'] = push_whitelist_usernames
    if require_signed_commits: args['require_signed_commits'] = require_signed_commits
    if required_approvals != 0: args['required_approvals'] = required_approvals
    if rule_name != "": args['rule_name'] = rule_name
    if status_check_contexts is not None: args['status_check_contexts'] = status_check_contexts
    if unprotected_file_patterns is not None: args['unprotected_file_patterns'] = unprotected_file_patterns
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_branch_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Update Branch Protection Priorities", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_update_branch_protection_priorities(owner: str, repo: str, protection_ids: list[int] | None = None, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update the priorities of branch protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        protection_ids: Branch protection IDs in priority order (e.g. ["value"]).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if protection_ids is not None: args['protection_ids'] = protection_ids
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_update_branch_protection_priorities', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Branch Protection", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_branch_protection(owner: str, repo: str, name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific branch protection for the repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        name: Resource name (e.g. my-resource).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Get Branch Protection", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_branch_protection(owner: str, repo: str, name: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific branch protection for the repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        name: Resource name (e.g. my-resource).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Edit Branch Protection", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_edit_branch_protection(owner: str, repo: str, name: str, approvals_whitelist_teams: list[str] | None = None, approvals_whitelist_usernames: list[str] | None = None, block_admin_merge_override: bool = False, block_on_official_review_requests: bool = False, block_on_outdated_branch: bool = False, block_on_rejected_reviews: bool = False, dismiss_stale_approvals: bool = False, enable_approvals_whitelist: bool = False, enable_force_push: bool = False, enable_force_push_allowlist: bool = False, enable_merge_whitelist: bool = False, enable_push: bool = False, enable_push_whitelist: bool = False, enable_status_check: bool = False, force_push_allowlist_deploy_keys: bool = False, force_push_allowlist_teams: list[str] | None = None, force_push_allowlist_usernames: list[str] | None = None, ignore_stale_approvals: bool = False, merge_whitelist_teams: list[str] | None = None, merge_whitelist_usernames: list[str] | None = None, priority: int = 0, protected_file_patterns: list[str] | None = None, push_whitelist_deploy_keys: bool = False, push_whitelist_teams: list[str] | None = None, push_whitelist_usernames: list[str] | None = None, require_signed_commits: bool = False, required_approvals: int = 0, status_check_contexts: list[str] | None = None, unprotected_file_patterns: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a branch protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        name: Resource name (e.g. my-resource).
        approvals_whitelist_teams: Team names whose approvals count (e.g. ["value"]).
        approvals_whitelist_usernames: Usernames whose approvals count (e.g. ["value"]).
        block_admin_merge_override: Whether to block admin merge override: true or false.
        block_on_official_review_requests: Whether to block on official review requests: true or false.
        block_on_outdated_branch: Whether to block merging on an outdated branch: true or false.
        block_on_rejected_reviews: Whether to block merging on rejected reviews: true or false.
        dismiss_stale_approvals: Whether to dismiss stale approvals: true or false.
        enable_approvals_whitelist: Whether to enable the approvals whitelist: true or false.
        enable_force_push: Whether to enable force pushes: true or false.
        enable_force_push_allowlist: Whether to enable the force-push allowlist: true or false.
        enable_merge_whitelist: Whether to enable the merge whitelist: true or false.
        enable_push: Whether to enable pushing: true or false.
        enable_push_whitelist: Whether to enable the push whitelist: true or false.
        enable_status_check: Whether to require status checks: true or false.
        force_push_allowlist_deploy_keys: Whether to allow force-push deploy keys: true or false.
        force_push_allowlist_teams: Team names allowed to force-push (e.g. ["value"]).
        force_push_allowlist_usernames: Usernames allowed to force-push (e.g. ["value"]).
        ignore_stale_approvals: Whether to ignore stale approvals: true or false.
        merge_whitelist_teams: Team names allowed to merge (e.g. ["value"]).
        merge_whitelist_usernames: Usernames allowed to merge (e.g. ["value"]).
        priority: Priority value (e.g. 1).
        protected_file_patterns: Protected file patterns (e.g. ["*.md", "docs/*"]).
        push_whitelist_deploy_keys: Whether to allow push deploy keys: true or false.
        push_whitelist_teams: Team names allowed to push (e.g. ["value"]).
        push_whitelist_usernames: Usernames allowed to push (e.g. ["value"]).
        require_signed_commits: Whether to require signed commits: true or false.
        required_approvals: Number of required approvals (e.g. 1).
        status_check_contexts: Required status check contexts (e.g. ["ci/build"]).
        unprotected_file_patterns: Unprotected file patterns (e.g. ["*.txt"]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['name'] = name
    if approvals_whitelist_teams is not None: args['approvals_whitelist_teams'] = approvals_whitelist_teams
    if approvals_whitelist_usernames is not None: args['approvals_whitelist_usernames'] = approvals_whitelist_usernames
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
    if protected_file_patterns is not None: args['protected_file_patterns'] = protected_file_patterns
    if push_whitelist_deploy_keys: args['push_whitelist_deploy_keys'] = push_whitelist_deploy_keys
    if push_whitelist_teams is not None: args['push_whitelist_teams'] = push_whitelist_teams
    if push_whitelist_usernames is not None: args['push_whitelist_usernames'] = push_whitelist_usernames
    if require_signed_commits: args['require_signed_commits'] = require_signed_commits
    if required_approvals != 0: args['required_approvals'] = required_approvals
    if status_check_contexts is not None: args['status_check_contexts'] = status_check_contexts
    if unprotected_file_patterns is not None: args['unprotected_file_patterns'] = unprotected_file_patterns
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_branch_protection', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo List Branches", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_branches(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's branches.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create Branch", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_branch(owner: str, repo: str, new_branch_name: str, old_branch_name: str = '', old_ref_name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a branch.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        new_branch_name: New branch name (e.g. feature).
        old_branch_name: Existing branch name to branch from (e.g. main).
        old_ref_name: Existing git reference to branch from (e.g. main).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Branch", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_branch(owner: str, repo: str, branch: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific branch from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        branch: Branch name (e.g. main).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Branch", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_branch(owner: str, repo: str, branch: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Retrieve a specific branch from a repository, including its effective branch protection.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        branch: Branch name (e.g. main).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Rename Branch", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_rename_branch(owner: str, repo: str, branch: str, name: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Rename a branch.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        branch: Branch name (e.g. main).
        name: Resource name (e.g. my-resource).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo List Collaborators", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_collaborators(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's collaborators.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Collaborator", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_collaborator(owner: str, repo: str, collaborator: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a collaborator from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        collaborator: Collaborator username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Check Collaborator", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_check_collaborator(owner: str, repo: str, collaborator: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a user is a collaborator of a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        collaborator: Collaborator username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Add Collaborator", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_add_collaborator(owner: str, repo: str, collaborator: str, permission: Literal['read', 'write', 'admin'] = 'read', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add or Update a collaborator to a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        collaborator: Collaborator username (e.g. amanda).
        permission: Permission level. Options: read, write, or admin.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['collaborator'] = collaborator
    if permission is not None and permission != 'read': args['permission'] = permission
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_add_collaborator', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Repo Permissions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_repo_permissions(owner: str, repo: str, collaborator: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get repository permissions for a user.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        collaborator: Collaborator username (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get All Commits", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_all_commits(owner: str, repo: str, start_ref: str = "", file_path: str = "", since: str = "", until: str = "", include_stats: bool = False, include_verification: bool = False, include_files: bool = False, page: int = 1, limit: int = 50, query_not: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a list of all commits from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        start_ref: Branch, tag, or commit SHA to start listing commits from.
        file_path: File or directory path.
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        until: ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_stats: Whether to include diff statistics: true or false.
        include_verification: Whether to include verification: true or false.
        include_files: File operation list. true or false.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        query_not: Commit query specifier to exclude.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if start_ref is not None and start_ref != "": args['start_ref'] = start_ref
    if file_path is not None and file_path != "": args['file_path'] = file_path
    if since is not None and since != "": args['since'] = since
    if until is not None and until != "": args['until'] = until
    if include_stats is not None and include_stats != "": args['include_stats'] = include_stats
    if include_verification is not None and include_verification != "": args['include_verification'] = include_verification
    if include_files is not None and include_files != "": args['include_files'] = include_files
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if query_not is not None and query_not != "": args['query_not'] = query_not
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_all_commits', get_user_token(), **args)
    return {'commits': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Get Combined Status By Ref", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_combined_status_by_ref(owner: str, repo: str, ref: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a commit's combined status, by branch/tag/commit reference.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Statuses By Ref", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_statuses_by_ref(owner: str, repo: str, ref: str, sort: Literal['oldest', 'recentupdate', 'leastupdate', 'leastindex', 'highestindex'] = 'oldest', state: Literal['pending', 'success', 'error', 'failure', 'warning'] = 'pending', page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a commit's statuses, by branch/tag/commit reference.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        sort: Sort field. Options: oldest, recentupdate, leastupdate, leastindex, or highestindex.
        state: State filter. Options: pending, success, error, failure, or warning.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Get Commit Pull Request", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_commit_pull_request(owner: str, repo: str, sha: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get the merged pull request of the commit.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Compare Diff", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_compare_diff(owner: str, repo: str, compare_range: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get commit comparison information.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        compare_range: Comparison range in base...head format. Options: base...head range (e.g. main...feature).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['compare_range'] = compare_range
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_compare_diff', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Contents List", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_contents_list(owner: str, repo: str, ref: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the metadata of all the entries of the root dir.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Change Files", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_change_files(owner: str, repo: str, operation: Literal['create', 'update', 'upload', 'rename', 'delete'], path: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, message: str = '', new_branch: str = '', signoff: bool = False, content: str = '', from_path: str = '', sha: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Modify multiple files in a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        author: Commit author identity.
        branch: Branch name (e.g. main).
        committer: Commit committer identity.
        dates: Commit author and committer dates.
        message: Commit message (e.g. Fix login bug).
        new_branch: New branch name (e.g. feature).
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message. true or false.
        operation: File operation. Options: create, update, upload, rename, or delete.
        path: File path relative to the repository root (e.g. docs/README.md).
        content: Plain-text file content.
        from_path: Original file path for a rename or move (e.g. old.txt).
        sha: Blob SHA for an existing file (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    if dates is not None: args['dates'] = dates
    if message != "": args['message'] = message
    if new_branch != "": args['new_branch'] = new_branch
    if signoff: args['signoff'] = signoff
    args['operation'] = operation
    args['path'] = path
    if content != "": args['content'] = content
    if from_path != "": args['from_path'] = from_path
    if sha != "": args['sha'] = sha
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_change_files', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete File", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_file(owner: str, repo: str, filepath: str, message: str, sha: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, new_branch: str = '', signoff: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a file in a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        filepath: File path relative to the repository root (e.g. docs/README.md).
        author: Commit author identity.
        branch: Branch name (e.g. main).
        committer: Commit committer identity.
        dates: Commit author and committer dates.
        message: Commit message (e.g. Fix login bug).
        new_branch: New branch name (e.g. feature).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message. true or false.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Contents", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_contents(owner: str, repo: str, filepath: str, ref: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the metadata and contents (if a file) of an entry in a repository, or a list of entries if a dir.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        filepath: File path relative to the repository root (e.g. docs/README.md).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create File", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_file(owner: str, repo: str, filepath: str, content: str, message: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a file in a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        filepath: File path relative to the repository root (e.g. docs/README.md).
        author: Commit author identity.
        branch: Branch name (e.g. main).
        committer: Commit committer identity.
        content: Plain-text file content (e.g. hello world).
        dates: Commit author and committer dates.
        message: Commit message (e.g. Fix login bug).
        new_branch: New branch name (e.g. feature).
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message. true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Update File", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_update_file(owner: str, repo: str, filepath: str, content: str, message: str, sha: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, from_path: str = '', new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a file in a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        filepath: File path relative to the repository root (e.g. docs/README.md).
        author: Commit author identity.
        branch: Branch name (e.g. main).
        committer: Commit committer identity.
        content: Plain-text file content (e.g. updated text).
        dates: Commit author and committer dates.
        from_path: Original file path for a rename or move (e.g. old.txt).
        message: Commit message (e.g. Fix login bug).
        new_branch: New branch name (e.g. feature).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message. true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Apply Diff Patch", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_apply_diff_patch(owner: str, repo: str, patch: str, author: Identity = None, branch: str = '', committer: Identity = None, dates: CommitDateOptions = None, message: str = '', new_branch: str = '', signoff: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Apply diff patch to repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        author: Commit author identity.
        branch: Branch name (e.g. main).
        committer: Commit committer identity.
        patch: Unified diff patch text.
        dates: Commit author and committer dates.
        message: Commit message (e.g. Fix login bug).
        new_branch: New branch name (e.g. feature).
        signoff: Add a Signed-off-by trailer by the committer at the end of the commit log message. true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if author is not None: args['author'] = author
    if branch != "": args['branch'] = branch
    if committer is not None: args['committer'] = committer
    args['patch'] = patch
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="List Forks", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def list_forks(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's forks.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Create Fork", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_fork(owner: str, repo: str, name: str = '', organization: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Fork a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        name: Resource name (e.g. my-resource).
        organization: organization name, if forking into an organization.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Get Blob", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_blob(owner: str, repo: str, sha: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the blob of a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Single Commit", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_single_commit(owner: str, repo: str, sha: str, include_stats: bool = False, include_verification: bool = False, include_files: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a single commit from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        include_stats: Whether to include diff statistics: true or false.
        include_verification: Whether to include verification: true or false.
        include_files: File operation list. true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    if include_stats is not None and include_stats != "": args['include_stats'] = include_stats
    if include_verification is not None and include_verification != "": args['include_verification'] = include_verification
    if include_files is not None and include_files != "": args['include_files'] = include_files
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_single_commit', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List All Git Refs", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_all_git_refs(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get specified ref or filtered repository's refs.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_all_git_refs', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Git Refs", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_git_refs(owner: str, repo: str, ref: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get specified ref or filtered repository's refs.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Get Annotated Tag", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_annotated_tag(owner: str, repo: str, sha: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the tag object of an annotated tag (not lightweight tags).

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Get Tree", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_tree(owner: str, repo: str, sha: str, recursive: bool = False, page: int = 1, per_page: int = 0, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the tree of a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        recursive: show all directories and files. true or false.
        page: Page number (1-based) (Default: 1).
        per_page: number of items per page (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Issue Templates", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_issue_templates(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get available issue templates for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_issue_templates', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue List Issues", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_list_issues(owner: str, repo: str, state: Literal['closed', 'open', 'all'] = 'closed', labels: list[str] | None = None, q: str = "", type: Literal['issues', 'pulls'] = 'issues', milestones: list[str] | None = None, since: str = "", before: str = "", created_by: str = "", assigned_by: str = "", mentioned_by: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's issues.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        state: State filter. Options: open, closed, or all.
        labels: Label names to filter by (e.g. ["bug", "ui"]).
        q: Search query.
        type: Issue type: issues or pulls.
        milestones: Milestone names or IDs to filter by (e.g. ["v1.0"]).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        created_by: Only show items which were created by the given user.
        assigned_by: Only show items for which the given user is assigned.
        mentioned_by: Only show items in which the given user was mentioned.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue Create Issue", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_create_issue(owner: str, repo: str, body: str, title: str, assignee: str = '', assignees: list[str] | None = None, closed: bool = False, due_date: str = '', labels: list[int] | None = None, milestone: int = 0, ref: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        assignee: Assignee username (e.g. amanda).
        assignees: List of usernames (e.g. ["amanda"]).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        closed: Whether the issue is closed: true or false.
        due_date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        labels: List of label IDs (e.g. [1, 2]).
        milestone: Milestone ID (e.g. 1).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Repo Comments", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_repo_comments(owner: str, repo: str, since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all comments in a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Comment", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_comment(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a comment.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Comment ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Comment", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_comment(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a comment.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Comment ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Edit Comment", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_edit_comment(owner: str, repo: str, id: int, body: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a comment.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Comment ID (e.g. 1).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Comment Reaction", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_comment_reaction(owner: str, repo: str, id: int, content: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a reaction from a comment of an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Comment ID (e.g. 1).
        content: Reaction content: +1, -1, laugh, hooray, confused, heart, rocket, or eyes.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Comment Reactions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_comment_reactions(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a list of reactions from a comment of an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Comment ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Post Comment Reaction", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_post_comment_reaction(owner: str, repo: str, id: int, content: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a reaction to a comment of an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Comment ID (e.g. 1).
        content: Reaction content: +1, -1, laugh, hooray, confused, heart, rocket, or eyes.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Pinned Issues", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_pinned_issues(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's pinned issues.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pinned_issues', get_user_token(), **args)
    return {'issues': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue Get Issue", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_issue(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Edit Issue", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_edit_issue(owner: str, repo: str, index: int, assignee: str = '', assignees: list[str] | None = None, body: str = '', due_date: str = '', milestone: int = 0, ref: str = '', state: Literal['open', 'closed'] = '', title: str = '', unset_due_date: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        assignee: Assignee username (e.g. amanda).
        assignees: List of usernames (e.g. ["amanda"]).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        due_date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        milestone: Milestone ID (e.g. 1).
        ref: Git reference (e.g. main, refs/heads/main, or a commit SHA).
        state: State filter. Options: open or closed.
        title: Title (e.g. Sprint planning).
        unset_due_date: Whether to clear the due date: true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    if state is not None and state != '': args['state'] = state
    if title != "": args['title'] = title
    if unset_due_date: args['unset_due_date'] = unset_due_date
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_issue', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Remove Issue Blocking", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_remove_issue_blocking(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unblock the issue given in the body by the issue in path.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number.
        body_index: Issue number (e.g. 1).
        body_owner: Repository owner username (e.g. solo).
        body_repo: Repository name (e.g. demo).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue List Blocks", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_list_blocks(owner: str, repo: str, index: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List issues that are blocked by this issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Create Issue Blocking", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_create_issue_blocking(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Block the issue given in the body by the issue in path.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number.
        body_index: Issue number (e.g. 1).
        body_owner: Repository owner username (e.g. solo).
        body_repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue Get Comments", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_comments(owner: str, repo: str, index: int, since: str = "", before: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all comments on an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue Create Comment", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_create_comment(owner: str, repo: str, index: int, body: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a comment to an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Comment Deprecated", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_comment_deprecated(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a comment.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        id: Comment ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Edit Comment Deprecated", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_edit_comment_deprecated(owner: str, repo: str, index: int, id: int, body: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a comment.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        id: Comment ID (e.g. 1).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Edit Issue Deadline", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_edit_issue_deadline(owner: str, repo: str, index: int, due_date: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Set an issue deadline.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        due_date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Remove Issue Dependencies", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_remove_issue_dependencies(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove an issue dependency.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number.
        body_index: Issue number (e.g. 1).
        body_owner: Repository owner username (e.g. solo).
        body_repo: Repository name (e.g. demo).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue List Issue Dependencies", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_list_issue_dependencies(owner: str, repo: str, index: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an issue's dependencies, i.e all issues that block this issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Create Issue Dependencies", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_create_issue_dependencies(owner: str, repo: str, index: str, body_index: int = 0, body_owner: str = '', body_repo: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Make the issue in the url depend on the issue in the form.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number.
        body_index: Issue number (e.g. 1).
        body_owner: Repository owner username (e.g. solo).
        body_repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Clear Labels", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_clear_labels(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove all labels from an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Labels", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_labels(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get an issue's labels.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Add Label", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_add_label(owner: str, repo: str, index: int, labels: list[int] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a label to an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        labels: List of label IDs (e.g. [1, 2]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Replace Labels", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_replace_labels(owner: str, repo: str, index: int, labels: list[int] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Replace an issue's labels.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        labels: List of label IDs (e.g. [1, 2]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Remove Label", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_remove_label(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a label from an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        id: Label ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Unlock Issue", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_unlock_issue(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unlock an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Lock Issue", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_lock_issue(owner: str, repo: str, index: int, lock_reason: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Lock an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        lock_reason: Reason for locking the issue (e.g. Off-topic discussion).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Unpin Issue", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def unpin_issue(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unpin an Issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Pin Issue", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def pin_issue(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Pin an Issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Move Issue Pin", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def move_issue_pin(owner: str, repo: str, index: int, position: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Moves the Pin to the given Position.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        position: Pin position (e.g. 2).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Issue Reaction", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_issue_reaction(owner: str, repo: str, index: int, content: str = '', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a reaction from an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        content: Reaction content: +1, -1, laugh, hooray, confused, heart, rocket, or eyes.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Issue Reactions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_issue_reactions(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a list reactions of an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Post Issue Reaction", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_post_issue_reaction(owner: str, repo: str, index: int, content: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a reaction to an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        content: Reaction content: +1, -1, laugh, hooray, confused, heart, rocket, or eyes.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Stop Watch", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_stop_watch(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete an issue's existing stopwatch.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Start Stop Watch", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_start_stop_watch(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Start stopwatch on an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Stop Stop Watch", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_stop_stop_watch(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Stop an issue's existing stopwatch.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Subscriptions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_subscriptions(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get users who subscribed on an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Check Subscription", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_check_subscription(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if user is subscribed to an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Subscription", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_subscription(owner: str, repo: str, index: int, user: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unsubscribe user from issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        user: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Add Subscription", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_add_subscription(owner: str, repo: str, index: int, user: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Subscribe user to issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        user: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Comments And Timeline", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_comments_and_timeline(owner: str, repo: str, index: int, since: str = "", page: int = 1, limit: int = 50, before: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all comments and events on an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Reset Time", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_reset_time(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Reset a tracked time of an issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Tracked Times", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_tracked_times(owner: str, repo: str, index: int, user: str = "", since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List an issue's tracked times.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        user: Username (e.g. amanda).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Add Time", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_add_time(owner: str, repo: str, index: int, time: int, created: str = '', user_name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add tracked time to a issue.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        created: ISO 8601 format (2026-06-22T15:00:00-04:00).
        time: Time in seconds (e.g. 3600).
        user_name: Username of the user who spent the time (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Time", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_time(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete specific tracked time.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        id: Resource ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Keys", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_keys(owner: str, repo: str, key_id: int = 0, fingerprint: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's keys.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        key_id: the key_id to search for (e.g. 1).
        fingerprint: fingerprint of the key.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Create Key", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_key(owner: str, repo: str, public_key: str, title: str, read_only: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a key to a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        public_key: SSH public key in authorized_keys format.
        read_only: Whether the token is read-only: true or false.
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['public_key'] = public_key
    if read_only: args['read_only'] = read_only
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_key', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Key", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_key(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a key from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Deploy key ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Get Key", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_key(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a repository's key by id.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Deploy key ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue List Labels", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_list_labels(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get all of a repository's labels.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Create Label", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_create_label(owner: str, repo: str, color: str, description: str, name: str, exclusive: bool = False, is_archived: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a label.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        color: Hex color code (e.g. #d73a4a).
        description: Description text (e.g. Short description).
        exclusive: Whether the label is exclusive: true or false.
        is_archived: Whether the label is archived: true or false.
        name: Resource name (e.g. my-resource).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Label", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_label(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a label.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Label ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Label", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_label(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a single label.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Label ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Edit Label", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_edit_label(owner: str, repo: str, id: int, color: str = '', description: str = '', exclusive: bool = False, is_archived: bool = False, name: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a label.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Label ID (e.g. 1).
        color: Hex color code (e.g. #d73a4a).
        description: Description text (e.g. Short description).
        exclusive: Whether the label is exclusive: true or false.
        is_archived: Whether the label is archived: true or false.
        name: Resource name (e.g. my-resource).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Languages", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_languages(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get languages and number of bytes of code written.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Licenses", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_licenses(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get repo licenses.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_licenses', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Merge Upstream", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_merge_upstream(owner: str, repo: str, branch: str = '', fast_forward_only: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Merge a branch from upstream.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        branch: Branch name (e.g. main).
        fast_forward_only: Whether to fast-forward only: true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if branch != "": args['branch'] = branch
    if fast_forward_only: args['fast_forward_only'] = fast_forward_only
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_merge_upstream', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Issue Get Milestones List", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_milestones_list(owner: str, repo: str, state: Literal['open', 'closed', 'all'] = '', name: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get all of a repository's opened milestones.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        state: State filter. Options: open, closed, or all.
        name: Resource name (e.g. my-resource).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Create Milestone", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def issue_create_milestone(owner: str, repo: str, description: str, title: str, due_on: str = '', state: Literal['open', 'closed'] = 'open', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a milestone.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        description: Description text (e.g. Short description).
        due_on: ISO 8601 format (2026-06-22T15:00:00-04:00).
        state: State filter. Options: open or closed.
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['description'] = description
    if due_on != "": args['due_on'] = due_on
    if state is not None and state != 'open': args['state'] = state
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_create_milestone', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Delete Milestone", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def issue_delete_milestone(owner: str, repo: str, id: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a milestone.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Milestone ID.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Get Milestone", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_get_milestone(owner: str, repo: str, id: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a milestone.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Milestone ID.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Issue Edit Milestone", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def issue_edit_milestone(owner: str, repo: str, id: str, description: str = '', due_on: str = '', state: Literal['open', 'closed'] = '', title: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a milestone.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Milestone ID.
        description: Description text (e.g. Short description).
        due_on: ISO 8601 format (2026-06-22T15:00:00-04:00).
        state: State filter. Options: open or closed.
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['id'] = id
    if description != "": args['description'] = description
    if due_on != "": args['due_on'] = due_on
    if state is not None and state != '': args['state'] = state
    if title != "": args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('issue_edit_milestone', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Notify Get Repo List", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_get_repo_list(owner: str, repo: str, all: bool = False, status_types: list[str] | None = None, subject_type: list[Literal['issue', 'pull', 'commit', 'repository']] | None = None, since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List users's notification threads on a specific repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        all: Whether to include all items: true or false.
        status_types: Notification status types. Options: unread, read, or pinned.
        subject_type: Notification subject types. Options: issue, pull, commit, or repository.
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status_types'] = status_types
    if subject_type is not None and subject_type != "": args['subject_type'] = subject_type
    if since is not None and since != "": args['since'] = since
    if before is not None and before != "": args['before'] = before
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_get_repo_list', get_user_token(), **args)
    return {'notifications': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Notify Read Repo List", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def notify_read_repo_list(owner: str, repo: str, all: str = "", status_types: list[str] | None = None, to_status: str = "", last_read_at: str = "", sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Mark notification threads as read, pinned or unread on a specific repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        all: Whether to include all items: true or false.
        status_types: Notification status types. Options: unread, read, or pinned.
        to_status: Target notification status. Options: read, unread, or pinned.
        last_read_at: ISO 8601 format (2026-06-22T15:00:00-04:00).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if all is not None and all != "": args['all'] = all
    if status_types is not None and status_types != "": args['status_types'] = status_types
    if to_status is not None and to_status != "": args['to_status'] = to_status
    if last_read_at is not None and last_read_at != "": args['last_read_at'] = last_read_at
    if sudo: args["sudo"] = sudo
    data = await get_client().call('notify_read_repo_list', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo List Pull Requests", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_pull_requests(owner: str, repo: str, base_branch: str = "", state: Literal['open', 'closed', 'all'] = 'open', sort: Literal['oldest', 'recentupdate', 'recentclose', 'leastupdate', 'mostcomment', 'leastcomment', 'priority'] = 'oldest', milestone: int = 0, labels: list[int] | None = None, poster_username: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's pull requests.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        base_branch: Target base branch (e.g. main).
        state: State filter. Options: open, closed, or all.
        sort: Sort field. Options: oldest, recentupdate, recentclose, leastupdate, mostcomment, leastcomment, or priority.
        milestone: Milestone ID (e.g. 1).
        labels: Label IDs to filter by (e.g. [1, 2]).
        poster_username: Pull request author username.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if base_branch is not None and base_branch != "": args['base_branch'] = base_branch
    if state is not None and state != "": args['state'] = state
    if sort is not None and sort != "": args['sort'] = sort
    if milestone is not None and milestone != "": args['milestone'] = milestone
    if labels is not None and labels != "": args['labels'] = labels
    if poster_username is not None and poster_username != "": args['poster_username'] = poster_username
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pull_requests', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Create Pull Request", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_pull_request(owner: str, repo: str, base: str, body: str, head: str, title: str, assignee: str = '', assignees: list[str] | None = None, due_date: str = '', labels: list[int] | None = None, milestone: int = 0, reviewers: list[str] | None = None, team_reviewers: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        assignee: Assignee username (e.g. amanda).
        assignees: List of usernames (e.g. ["amanda"]).
        base: Base branch name (e.g. main).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        due_date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        head: Head branch name (e.g. feature).
        labels: List of label IDs (e.g. [1, 2]).
        milestone: Milestone ID (e.g. 1).
        reviewers: List of reviewer usernames (e.g. ["amanda"]).
        team_reviewers: List of reviewer team names (e.g. ["developers"]).
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Pinned Pull Requests", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_pinned_pull_requests(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's pinned pull requests.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_pinned_pull_requests', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Pull Request By Base Head", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_pull_request_by_base_head(owner: str, repo: str, base: str, head: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a pull request by base and head.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        base: Base branch name (e.g. main).
        head: Head branch name (e.g. feature).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Pull Request", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_pull_request(owner: str, repo: str, index: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Edit Pull Request", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_edit_pull_request(owner: str, repo: str, index: int, allow_maintainer_edit: bool = False, assignee: str = '', assignees: list[str] | None = None, base: str = '', body: str = '', due_date: str = '', labels: list[int] | None = None, milestone: int = 0, state: Literal['open', 'closed'] = '', title: str = '', unset_due_date: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        allow_maintainer_edit: Whether to allow maintainer edits. true or false.
        assignee: Assignee username (e.g. amanda).
        assignees: List of usernames (e.g. ["amanda"]).
        base: Base branch name (e.g. main).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        due_date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        labels: List of label IDs (e.g. [1, 2]).
        milestone: Milestone ID (e.g. 1).
        state: State filter. Options: open or closed.
        title: Title (e.g. Sprint planning).
        unset_due_date: Whether to clear the due date: true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    if state is not None and state != '': args['state'] = state
    if title != "": args['title'] = title
    if unset_due_date: args['unset_due_date'] = unset_due_date
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Pull Request Commits", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_pull_request_commits(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_verification: bool = False, include_files: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get commits for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_verification: Whether to include verification: true or false.
        include_files: File operation list. true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    if include_verification is not None and include_verification != "": args['include_verification'] = include_verification
    if include_files is not None and include_files != "": args['include_files'] = include_files
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_request_commits', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Pull Request Files", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_pull_request_files(owner: str, repo: str, index: int, skip_to: str = "", whitespace: Literal['ignore-all', 'ignore-change', 'ignore-eol', 'show-all'] = 'ignore-all', page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get changed files for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        skip_to: Commit SHA to skip to.
        whitespace: whitespace behavior. Options: ignore-all, ignore-change, ignore-eol, or show-all.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if skip_to is not None and skip_to != "": args['skip_to'] = skip_to
    if whitespace is not None and whitespace != "": args['whitespace'] = whitespace
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_pull_request_files', get_user_token(), **args)
    return {'pull_requests': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Cancel Scheduled Auto Merge", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_cancel_scheduled_auto_merge(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Cancel the scheduled auto merge for the given pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Issue number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Pull Request Is Merged", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_pull_request_is_merged(owner: str, repo: str, index: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a pull request has been merged.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Merge Pull Request", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_merge_pull_request(owner: str, repo: str, index: int, do: Literal['merge', 'rebase', 'rebase-merge', 'squash', 'fast-forward-only', 'manually-merged'], merge_commit_id: str = '', merge_message_field: str = '', merge_title_field: str = '', delete_branch_after_merge: bool = False, force_merge: bool = False, head_commit_id: str = '', merge_when_checks_succeed: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Merge a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        do: Merge method. Options: merge, rebase, rebase-merge, squash, fast-forward-only, or manually-merged.
        merge_commit_id: Merge commit SHA.
        merge_message_field: Merge commit message.
        merge_title_field: Merge commit title.
        delete_branch_after_merge: Whether to delete the head branch after merging: true or false.
        force_merge: Whether to force the merge: true or false.
        head_commit_id: Expected head commit SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        merge_when_checks_succeed: Whether to merge automatically when checks succeed: true or false.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['do'] = do
    if merge_commit_id != "": args['merge_commit_id'] = merge_commit_id
    if merge_message_field != "": args['merge_message_field'] = merge_message_field
    if merge_title_field != "": args['merge_title_field'] = merge_title_field
    if delete_branch_after_merge: args['delete_branch_after_merge'] = delete_branch_after_merge
    if force_merge: args['force_merge'] = force_merge
    if head_commit_id != "": args['head_commit_id'] = head_commit_id
    if merge_when_checks_succeed: args['merge_when_checks_succeed'] = merge_when_checks_succeed
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_merge_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Pull Review Requests", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_pull_review_requests(owner: str, repo: str, index: int, reviewers: list[str] | None = None, team_reviewers: list[str] | None = None, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Cancel review requests for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        reviewers: List of reviewer usernames (e.g. ["amanda"]).
        team_reviewers: List of reviewer team names (e.g. ["developers"]).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create Pull Review Requests", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_pull_review_requests(owner: str, repo: str, index: int, reviewers: list[str] | None = None, team_reviewers: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create review requests for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        reviewers: List of reviewer usernames (e.g. ["amanda"]).
        team_reviewers: List of reviewer team names (e.g. ["developers"]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo List Pull Reviews", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_pull_reviews(owner: str, repo: str, index: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all reviews for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create Pull Review", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_pull_review(owner: str, repo: str, index: int, review_body: str, review_event: Literal['APPROVED', 'PENDING', 'COMMENT', 'REQUEST_CHANGES', 'REQUEST_REVIEW'], review_commit_id: str = '', comment_path: str = '', comment_body: str = '', comment_new_position: int = 0, comment_old_position: int = 0, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a review to an pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        review_body: Review body text in Markdown.
        review_commit_id: Commit SHA for the review.
        review_event: Review event. Options: APPROVED, PENDING, COMMENT, REQUEST_CHANGES, or REQUEST_REVIEW.
        comment_path: File path for the review comment (e.g. src/main.py).
        comment_body: Review comment text (e.g. Please add unit tests).
        comment_new_position: Line number in the new file version, or 0 (e.g. 1).
        comment_old_position: Line number in the old file version, or 0 (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['review_body'] = review_body
    if review_commit_id != "": args['review_commit_id'] = review_commit_id
    args['review_event'] = review_event
    if comment_path != "": args['comment_path'] = comment_path
    if comment_body != "": args['comment_body'] = comment_body
    if comment_new_position != 0: args['comment_new_position'] = comment_new_position
    if comment_old_position != 0: args['comment_old_position'] = comment_old_position
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Pull Review", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_pull_review(owner: str, repo: str, index: int, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific review from a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        id: Review ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Pull Review", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_pull_review(owner: str, repo: str, index: int, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific review for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        id: Review ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Submit Pull Review", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_submit_pull_review(owner: str, repo: str, index: int, id: int, review_body: str = '', review_event: Literal['APPROVED', 'COMMENT', 'REQUEST_CHANGES'] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Submit a pending review to an pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        id: Review ID (e.g. 1).
        review_body: Body text in Markdown (e.g. Steps to reproduce...).
        review_event: Review event. Options: APPROVED, PENDING, COMMENT, REQUEST_CHANGES, or REQUEST_REVIEW.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if review_body != "": args['review_body'] = review_body
    if review_event is not None and review_event != None: args['review_event'] = review_event
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_submit_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Pull Review Comments", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_pull_review_comments(owner: str, repo: str, index: int, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific review for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        id: Comment ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Dismiss Pull Review", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_dismiss_pull_review(owner: str, repo: str, index: int, id: int, dismiss_message: str = '', dismiss_prior_reviews: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Dismiss a review for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        id: Review ID (e.g. 1).
        dismiss_message: Dismissal message.
        dismiss_prior_reviews: Whether to dismiss prior reviews: true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    args['id'] = id
    if dismiss_message != "": args['dismiss_message'] = dismiss_message
    if dismiss_prior_reviews: args['dismiss_prior_reviews'] = dismiss_prior_reviews
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_dismiss_pull_review', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Un Dismiss Pull Review", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_un_dismiss_pull_review(owner: str, repo: str, index: int, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Cancel to dismiss a review for a pull request.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        id: Review ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Update Pull Request", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_update_pull_request(owner: str, repo: str, index: int, update_style: Literal['merge', 'rebase'] = 'merge', sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Merge PR's baseBranch into headBranch.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        index: Pull request number (e.g. 1).
        update_style: Update style. Options: merge or rebase.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['index'] = index
    if update_style is not None and update_style != "": args['update_style'] = update_style
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_update_pull_request', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo List Releases", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_releases(owner: str, repo: str, draft: bool = False, pre_release: bool = False, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's releases.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        draft: Whether the release is a draft: true or false.
        pre_release: filter (exclude / include) pre-releases. true or false.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if draft is not None and draft != "": args['draft'] = draft
    if pre_release is not None and pre_release != "": args['pre_release'] = pre_release
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_releases', get_user_token(), **args)
    return {'releases': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create Release", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_release(owner: str, repo: str, body: str, tag_name: str, draft: bool = False, name: str = '', prerelease: bool = False, tag_message: str = '', target_commitish: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a release.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        draft: Whether the release is a draft: true or false.
        name: Resource name (e.g. my-resource).
        prerelease: Whether the release is a prerelease: true or false.
        tag_message: Annotated tag message (e.g. Release 1.0.0).
        tag_name: Tag name (e.g. v1.0.0).
        target_commitish: Branch or commit SHA the tag or release targets (e.g. main).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Latest Release", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_latest_release(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Gets the most recent non-prerelease, non-draft release of a repository, sorted by created_at.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Release By Tag", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_release_by_tag(owner: str, repo: str, tag: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a release by tag name.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        tag: Tag name (e.g. v1.0.0).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Release By Tag", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_release_by_tag(owner: str, repo: str, tag: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a release by tag name.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        tag: Tag name (e.g. v1.0.0).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Release", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_release(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a release.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Release ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Release", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_release(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a release.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Release ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Edit Release", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_edit_release(owner: str, repo: str, id: int, body: str = '', draft: bool = False, name: str = '', prerelease: bool = False, tag_name: str = '', target_commitish: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Update a release.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Release ID (e.g. 1).
        body: Body text in Markdown (e.g. Steps to reproduce...).
        draft: Whether the release is a draft: true or false.
        name: Resource name (e.g. my-resource).
        prerelease: Whether the release is a prerelease: true or false.
        tag_name: Tag name (e.g. v1.0.0).
        target_commitish: Branch or commit SHA the tag or release targets (e.g. main).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Reviewers", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_reviewers(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Return all users that can be requested to review in this repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_reviewers', get_user_token(), **args)
    return {'repositories': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Statuses", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_statuses(owner: str, repo: str, sha: str, sort: Literal['oldest', 'recentupdate', 'leastupdate', 'leastindex', 'highestindex'] = 'oldest', state: Literal['pending', 'success', 'error', 'failure', 'warning'] = 'pending', page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a commit's statuses.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        sort: Sort field. Options: oldest, recentupdate, leastupdate, leastindex, or highestindex.
        state: State filter. Options: pending, success, error, failure, or warning.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Create Status", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_status(owner: str, repo: str, sha: str, state: Literal['pending', 'success', 'error', 'failure', 'warning', 'skipped'], status_context: str = '', status_description: str = '', target_url: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a commit status.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sha: Commit or blob SHA (e.g. 0c7c3302299b0d70fd8d60bbd4f059b38d681b64).
        status_context: Status context identifier (e.g. ci/build).
        status_description: Short status description (e.g. All checks passed).
        state: Commit status state. Options: pending, success, error, failure, warning, or skipped.
        target_url: URL with more details (e.g. https://ci.example.com/build/123).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['sha'] = sha
    if status_context != "": args['status_context'] = status_context
    if status_description != "": args['status_description'] = status_description
    args['state'] = state
    if target_url != "": args['target_url'] = target_url
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_status', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current Delete Subscription", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def user_current_delete_subscription(owner: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unwatch a repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_delete_subscription', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current Check Subscription", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_check_subscription(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if the current user is watching a repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current Put Subscription", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_put_subscription(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Watch a repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Tag Protection", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_tag_protection(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List tag protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_tag_protection', get_user_token(), **args)
    return {'tag_protections': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Create Tag Protection", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_tag_protection(owner: str, repo: str, name_pattern: str, whitelist_teams: list[str] | None = None, whitelist_usernames: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a tag protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        name_pattern: Tag name pattern (e.g. v*).
        whitelist_teams: List of team names allowed to create matching tags (e.g. ["value"]).
        whitelist_usernames: List of usernames allowed to create matching tags (e.g. ["value"]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Tag Protection", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_tag_protection(owner: str, repo: str, id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a specific tag protection for the repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Tag protection ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Get Tag Protection", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_tag_protection(owner: str, repo: str, id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a specific tag protection for the repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Tag protection ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Edit Tag Protection", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_edit_tag_protection(owner: str, repo: str, id: int, name_pattern: str = '', whitelist_teams: list[str] | None = None, whitelist_usernames: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a tag protections for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        id: Tag protection ID (e.g. 1).
        name_pattern: Tag name pattern (e.g. v*).
        whitelist_teams: List of team names allowed to create matching tags (e.g. ["value"]).
        whitelist_usernames: List of usernames allowed to create matching tags (e.g. ["value"]).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo List Tags", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_tags(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's tags.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create Tag", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_tag(owner: str, repo: str, tag_name: str, message: str = '', target: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a new git tag in a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        message: Commit message (e.g. Fix login bug).
        tag_name: Tag name (e.g. v1.0.0).
        target: Target username (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Tag", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_tag(owner: str, repo: str, tag: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a repository's tag by name.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        tag: Tag name (e.g. v1.0.0).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Get Tag", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_tag(owner: str, repo: str, tag: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get the tag of a repository by tag name.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        tag: Tag name (e.g. v1.0.0).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo List Teams", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_teams(owner: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repository's teams.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_list_teams', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Team", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_team(owner: str, repo: str, team: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a team from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        team: Team name (e.g. developers).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Check Team", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_check_team(owner: str, repo: str, team: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if a team is assigned to a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        team: Team name (e.g. developers).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Add Team", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_add_team(owner: str, repo: str, team: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a team to a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        team: Team name (e.g. developers).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Tracked Times", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_tracked_times(owner: str, repo: str, user: str = "", since: str = "", before: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a repo's tracked times.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        user: Username (e.g. amanda).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User Tracked Times", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_tracked_times(owner: str, repo: str, user: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a user's tracked times in a repo.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        user: Username (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo List Topics", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_list_topics(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get list of topics that a repository has.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Update Topics", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_update_topics(owner: str, repo: str, topics: list[str] | None = None, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Replace list of topics for a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        topics: List of topic names (e.g. ["value"]).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Topic", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_topic(owner: str, repo: str, topic: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a topic from a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        topic: Topic name.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Add Topic", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_add_topic(owner: str, repo: str, topic: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a topic to a repository.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        topic: Topic name.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Create Wiki Page", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def repo_create_wiki_page(owner: str, repo: str, content: str, title: str, message: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a wiki page.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        content: Plain-text wiki page content (e.g. Welcome to the wiki).
        message: Commit message (e.g. Fix login bug).
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['content'] = content
    if message != "": args['message'] = message
    args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_create_wiki_page', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Delete Wiki Page", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def repo_delete_wiki_page(owner: str, repo: str, pageName: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a wiki page.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        pageName: name of the page.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Wiki Page", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_wiki_page(owner: str, repo: str, pageName: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a wiki page.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        pageName: name of the page.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Repo Edit Wiki Page", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_edit_wiki_page(owner: str, repo: str, pageName: str, content: str = '', message: str = '', title: str = '', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a wiki page.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        pageName: name of the page.
        content: Plain-text wiki page content (e.g. Updated wiki text).
        message: Commit message (e.g. Fix login bug).
        title: Title (e.g. Sprint planning).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['owner'] = owner
    args['repo'] = repo
    args['pageName'] = pageName
    if content != "": args['content'] = content
    if message != "": args['message'] = message
    if title != "": args['title'] = title
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_edit_wiki_page', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get Wiki Pages", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_wiki_pages(owner: str, repo: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get all wiki pages.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Repo Get Wiki Page Revisions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_wiki_page_revisions(owner: str, repo: str, pageName: str, page: int = 1, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get revisions of a wiki page.

    Args:
        owner: Repository owner username (e.g. solo).
        repo: Repository name (e.g. demo).
        pageName: name of the page.
        page: Page number (1-based) (Default: 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Generate Repo", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def generate_repo(template_owner: str, template_repo: str, description: str, name: str, owner: str, avatar: bool = False, default_branch: str = '', git_content: bool = False, git_hooks: bool = False, labels: bool = False, private: bool = False, protected_branch: bool = False, topics: bool = False, webhooks: bool = False, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository using a template.

    Args:
        template_owner: Template repository owner.
        template_repo: Template repository name.
        avatar: Whether to copy the avatar: true or false.
        default_branch: Default branch name (e.g. main).
        description: Description text (e.g. Short description).
        git_content: Whether to copy git content: true or false.
        git_hooks: Whether to copy git hooks: true or false.
        labels: List of label IDs (e.g. [1, 2]). true or false.
        name: Resource name (e.g. my-resource).
        owner: Repository owner username (e.g. solo).
        private: Whether the repository is private: true or false.
        protected_branch: Whether to copy protected branches: true or false.
        topics: List of topic names. true or false.
        webhooks: Whether to copy webhooks: true or false.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Repo Get By Id", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def repo_get_by_id(id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a repository by id.

    Args:
        id: Resource ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('repo_get_by_id', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Delete Team", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_delete_team(id: int, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Delete a team.

    Args:
        id: Team ID (e.g. 1).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_delete_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Get Team", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_get_team(id: int, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a team.

    Args:
        id: Team ID (e.g. 1).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_get_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Edit Team", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_edit_team(id: int, name: str, can_create_org_repo: bool = False, description: str = '', includes_all_repositories: bool = False, permission: Literal['read', 'write', 'admin'] = 'read', units: list[str] | None = None, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Edit a team.

    Args:
        id: Team ID (e.g. 1).
        can_create_org_repo: Whether the team may create organization repositories: true or false.
        description: Description text (e.g. Short description).
        includes_all_repositories: Whether the team includes all repositories: true or false.
        name: Resource name (e.g. my-resource).
        permission: Permission level. Options: read, write, or admin.
        units: Repository units granted to the team. Options: repo.code, repo.issues, repo.ext_issues, repo.pulls, repo.releases, repo.wiki, repo.ext_wiki, repo.projects, repo.packages, or repo.actions.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    if can_create_org_repo: args['can_create_org_repo'] = can_create_org_repo
    if description != "": args['description'] = description
    if includes_all_repositories: args['includes_all_repositories'] = includes_all_repositories
    args['name'] = name
    if permission is not None and permission != 'read': args['permission'] = permission
    if units is not None: args['units'] = units
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_edit_team', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Org List Team Activity Feeds", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_team_activity_feeds(id: int, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a team's activity feeds.

    Args:
        id: Team ID (e.g. 1).
        date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Team Members", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_team_members(id: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a team's members.

    Args:
        id: Team ID (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Remove Team Member", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_remove_team_member(id: int, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a team member.

    Args:
        id: Team ID (e.g. 1).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_remove_team_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Team Member", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_team_member(id: int, username: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a particular member of team.

    Args:
        id: Team ID (e.g. 1).
        username: Username (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Add Team Member", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_add_team_member(id: int, username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a team member.

    Args:
        id: Team ID (e.g. 1).
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['id'] = id
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_add_team_member', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Team Repos", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_team_repos(id: int, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a team's repos.

    Args:
        id: Team ID (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Remove Team Repository", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def org_remove_team_repository(id: int, org: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Remove a repository from a team.

    Args:
        id: Team ID (e.g. 1).
        org: Organization name (e.g. acme).
        repo: Repository name (e.g. demo).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Team Repo", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_team_repo(id: int, org: str, repo: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a particular repo of team.

    Args:
        id: Team ID (e.g. 1).
        org: Organization name (e.g. acme).
        repo: Repository name (e.g. demo).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Add Team Repository", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_add_team_repository(id: int, org: str, repo: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Add a repository to a team.

    Args:
        id: Team ID (e.g. 1).
        org: Organization name (e.g. acme).
        repo: Repository name (e.g. demo).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Topic Search", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def topic_search(q: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search topics via keyword.

    Args:
        q: Search query.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="User Get Current", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_get_current(include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get the authenticated user.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get_current', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current List Followers", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_list_followers(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the authenticated user's followers.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_followers', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current List Following", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_list_following(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the users that the authenticated user is following.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_following', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current Delete Follow", readOnlyHint=False, destructiveHint=True, idempotentHint=True, openWorldHint=False)
)
async def user_current_delete_follow(username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Unfollow a user.

    Args:
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_delete_follow', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current Check Following", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_check_following(username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check whether a user is followed by the authenticated user.

    Args:
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_check_following', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current Put Follow", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_put_follow(username: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Follow a user.

    Args:
        username: Username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_put_follow', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List Current User Orgs", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_current_user_orgs(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the current user's organizations.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('org_list_current_user_orgs', get_user_token(), **args)
    return {'organizations': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current List Repos", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_list_repos(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the repos that the authenticated user owns.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_repos', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Create Current User Repo", readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=False)
)
async def create_current_user_repo(description: str, name: str, auto_init: bool = False, default_branch: str = '', gitignores: str = '', issue_labels: str = '', license: str = '', object_format_name: Literal['sha1', 'sha256'] = 'sha1', private: bool = False, readme: str = '', template: bool = False, trust_model: Literal['default', 'collaborator', 'committer', 'collaboratorcommitter'] = 'default', include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Create a repository.

    Args:
        auto_init: Whether to initialize the repository: true or false.
        default_branch: Default branch name (e.g. main).
        description: Description text (e.g. Short description).
        gitignores: Gitignore template name.
        issue_labels: Issue label template name.
        license: License template name.
        name: Resource name (e.g. my-resource).
        object_format_name: Git object format. Options: sha1 or sha256.
        private: Whether the repository is private: true or false.
        readme: Readme template name.
        template: Whether the repository is a template: true or false.
        trust_model: Repository trust model. Options: default, collaborator, committer, or collaboratorcommitter.
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if auto_init: args['auto_init'] = auto_init
    if default_branch != "": args['default_branch'] = default_branch
    args['description'] = description
    if gitignores != "": args['gitignores'] = gitignores
    if issue_labels != "": args['issue_labels'] = issue_labels
    if license != "": args['license'] = license
    args['name'] = name
    if object_format_name is not None and object_format_name != 'sha1': args['object_format_name'] = object_format_name
    if private: args['private'] = private
    if readme != "": args['readme'] = readme
    if template: args['template'] = template
    if trust_model is not None and trust_model != 'default': args['trust_model'] = trust_model
    args["include_all_fields"] = ALLOW_ALL_AGGREGATE
    if sudo: args["sudo"] = sudo
    data = await get_client().call('create_current_user_repo', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current List Starred", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_list_starred(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """The repos that the authenticated user has starred.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_starred', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User Get Stop Watches", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_get_stop_watches(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get list of all existing stopwatches.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get_stop_watches', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Current List Subscriptions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_list_subscriptions(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List repositories watched by the authenticated user.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_current_list_subscriptions', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User List Teams", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_teams(page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List all the teams a user belongs to.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_teams', get_user_token(), **args)
    return {'teams': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User Current Tracked Times", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_current_tracked_times(page: int = 1, limit: int = 50, since: str = "", before: str = "", include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the current user's tracked times.

    Args:
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        since: ISO 8601 format (2026-06-22T15:00:00-04:00).
        before: ISO 8601 format (2026-06-22T15:00:00-04:00).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="User Search", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_search(q: str = "", uid: int = 0, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Search for users.

    Args:
        q: Search query.
        uid: User ID (e.g. 1).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="User Get", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_get(username: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a user.

    Args:
        username: Username (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User List Activity Feeds", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_activity_feeds(username: str, only_performed_by: bool = False, date: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a user's activity feeds.

    Args:
        username: Username (e.g. amanda).
        only_performed_by: Whether to only include actions performed by the user: true or false.
        date: ISO 8601 format (2026-06-22T15:00:00-04:00).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    if only_performed_by is not None and only_performed_by != "": args['only_performed_by'] = only_performed_by
    if date is not None and date != "": args['date'] = date
    if page is not None and page != "": args['page'] = page
    if limit is not None and limit != "": args['limit'] = limit
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_list_activity_feeds', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User List Followers", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_followers(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the given user's followers.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User List Following", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_following(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the users that the given user is following.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User Check Following", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_check_following(username: str, target: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Check if one user is following another user.

    Args:
        username: Username (e.g. amanda).
        target: Target username (e.g. amanda).
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args['target'] = target
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_check_following', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User List Gpg Keys", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_gpg_keys(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the given user's GPG keys.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User Get Heatmap Data", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_get_heatmap_data(username: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get a user's heatmap.

    Args:
        username: Username (e.g. amanda).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args['username'] = username
    args["include_all_fields"] = include_all_fields if ALLOW_ALL_AGGREGATE else False
    if sudo: args["sudo"] = sudo
    data = await get_client().call('user_get_heatmap_data', get_user_token(), **args)
    return {'users': json_to_toon(data)}

@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="User List Keys", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_keys(username: str, fingerprint: str = "", page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the given user's public keys.

    Args:
        username: Username (e.g. amanda).
        fingerprint: fingerprint of the key.
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org List User Orgs", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_list_user_orgs(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List a user's organizations.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="Org Get User Permissions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def org_get_user_permissions(username: str, org: str, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Get user permissions in organization.

    Args:
        username: Username (e.g. amanda).
        org: Organization name (e.g. acme).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User List Repos", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_repos(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the repos owned by the given user.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User List Starred", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_starred(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """The repos that the given user has starred.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"primary", "gitea"}, annotations=ToolAnnotations(title="User List Subscriptions", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def user_list_subscriptions(username: str, page: int = 1, limit: int = 50, include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """List the repositories watched by a user.

    Args:
        username: Username (e.g. amanda).
        page: Page number (1-based) (Default: 1).
        limit: Page size (1-50) (Default: 50).
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
    tags={"basic", "gitea"}, annotations=ToolAnnotations(title="Get Version", readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def get_version(include_all_fields: bool = False, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Returns the version of the Gitea application.

    Args:
        include_all_fields: Default False (common fields only). Set True for all fields.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
    """
    args: dict[str, Any] = {}
    args["include_all_fields"] = include_all_fields
    if sudo: args["sudo"] = sudo
    data = await get_client().call('get_version', get_user_token(), **args)
    if isinstance(data, list): return {"items": data}
    return data


@mcp.tool(
    tags={"advanced", "gitea"}, annotations=ToolAnnotations(title="Upload Generic Package", readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=False)
)
async def upload_generic_package(owner: str, package_name: str, version: str, filename: str,
                                 content: str, sudo: str = "", ctx: Context = None) -> dict[str, Any]:
    """Upload a text file as a Gitea generic package.

    Args:
        owner: Package owner username or organization name (e.g. solo).
        package_name: Generic package name (e.g. demo-package).
        version: Package version (e.g. 1.0.0).
        filename: File name stored in the package (e.g. readme.txt).
        content: Plain-text file content.
        sudo: Admin-only username to impersonate (e.g. amanda; Default: empty).
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
