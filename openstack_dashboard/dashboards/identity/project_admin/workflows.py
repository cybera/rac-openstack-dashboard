# Copyright 2012 United States Government as represented by the
# Administrator of the National Aeronautics and Space Administration.
# All Rights Reserved.
#
# Copyright 2012 Nebula, Inc.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.


from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _

from openstack_auth import utils as auth_utils

from horizon import exceptions
from horizon import forms
from horizon import messages
from horizon.utils import memoized
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.api import base
from openstack_dashboard.api import cinder
from openstack_dashboard.api import keystone
from openstack_dashboard.api import nova
from openstack_dashboard.usage import quotas

INDEX_URL = "horizon:identity:project_admin:index"
ADD_USER_URL = "horizon:identity:project_admin:create_user"
PROJECT_GROUP_ENABLED = keystone.VERSIONS.active >= 3
PROJECT_USER_MEMBER_SLUG = "update_members"
PROJECT_GROUP_MEMBER_SLUG = "update_group_members"
COMMON_HORIZONTAL_TEMPLATE = "identity/project_admin/_common_horizontal_form.html"


class CreateProjectInfoAction(workflows.Action):
    # Hide the domain_id and domain_name by default
    domain_id = forms.CharField(label=_("Domain ID"),
                                required=False,
                                widget=forms.HiddenInput())
    domain_name = forms.CharField(label=_("Domain Name"),
                                  required=False,
                                  widget=forms.HiddenInput())
    name = forms.CharField(label=_("Name"),
                           max_length=64)
    description = forms.CharField(widget=forms.widgets.Textarea(
                                  attrs={'rows': 4}),
                                  label=_("Description"),
                                  required=False)
    enabled = forms.BooleanField(label=_("Enabled"),
                                 required=False,
                                 initial=True)

    def __init__(self, request, *args, **kwargs):
        super(CreateProjectInfoAction, self).__init__(request,
                                                      *args,
                                                      **kwargs)
        # For keystone V3, display the two fields in read-only
        if keystone.VERSIONS.active >= 3:
            readonlyInput = forms.TextInput(attrs={'readonly': 'readonly'})
            self.fields["domain_id"].widget = readonlyInput
            self.fields["domain_name"].widget = readonlyInput

    class Meta(object):
        name = _("Project Information")
        help_text = _("Create a project to organize users.")


class CreateProjectInfo(workflows.Step):
    action_class = CreateProjectInfoAction
    template_name = COMMON_HORIZONTAL_TEMPLATE
    contributes = ("domain_id",
                   "domain_name",
                   "project_id",
                   "name",
                   "description",
                   "enabled")


class UpdateProjectMembersAction(workflows.MembershipAction):
    def __init__(self, request, *args, **kwargs):
        super(UpdateProjectMembersAction, self).__init__(request,
                                                         *args,
                                                         **kwargs)
        err_msg = _('Unable to retrieve user list. Please try again later.')
        # Use the domain_id from the project
        domain_id = self.initial.get("domain_id", None)
        project_id = ''
        if 'project_id' in self.initial:
            project_id = self.initial['project_id']

        # Get the default role
        try:
            default_role = api.keystone.get_default_role(self.request)
            # Default role is necessary to add members to a project
            if default_role is None:
                default = getattr(settings,
                                  "OPENSTACK_KEYSTONE_DEFAULT_ROLE", None)
                msg = (_('Could not find default role "%s" in Keystone') %
                       default)
                raise exceptions.NotFound(msg)
        except Exception:
            exceptions.handle(self.request,
                              err_msg,
                              redirect=reverse(INDEX_URL))
        default_role_name = self.get_default_role_field_name()
        self.fields[default_role_name] = forms.CharField(required=False)
        self.fields[default_role_name].initial = default_role.id

        # Get list of available users
        all_users = []
        try:
            if request.method == "POST":
                all_users = api.keystone.user_list(request,
                                                   domain=domain_id)
            else:
                all_users = api.keystone.user_list(request,
                                                   domain=domain_id,
                                                   project=project_id)
        except Exception:
            exceptions.handle(request, err_msg)
        users_list = [(user.id, user.name) for user in all_users]

        # Get list of roles
        role_list = []
        try:
            role_list = api.keystone.role_list(request)
        except Exception:
            exceptions.handle(request,
                              err_msg,
                              redirect=reverse(INDEX_URL))
        for role in role_list:
            field_name = self.get_member_field_name(role.id)
            label = role.name
            self.fields[field_name] = forms.MultipleChoiceField(required=False,
                                                                label=label)
            self.fields[field_name].choices = users_list
            self.fields[field_name].initial = []

        # Figure out users & roles
        if project_id:
            try:
                users_roles = api.keystone.get_project_users_roles(request,
                                                                   project_id)
            except Exception:
                exceptions.handle(request,
                                  err_msg,
                                  redirect=reverse(INDEX_URL))

            for user_id in users_roles:
                roles_ids = users_roles[user_id]
                for role_id in roles_ids:
                    field_name = self.get_member_field_name(role_id)
                    self.fields[field_name].initial.append(user_id)

    class Meta(object):
        name = _("Project Members")
        slug = PROJECT_USER_MEMBER_SLUG


class UpdateProjectMembers(workflows.UpdateMembersStep):
    action_class = UpdateProjectMembersAction
    template_name = "horizon/common/_workflow_step_update_members_cybera.html"
    depends_on = ("project_id",)
    show_roles = False
    available_list_title = _("All Users")
    members_list_title = _("Project Members")
    no_available_text = _("No users found.")
    no_members_text = _("No users.")

    def contribute(self, data, context):
        if data:
            try:
                roles = api.keystone.role_list(self.workflow.request)
            except Exception:
                exceptions.handle(self.workflow.request,
                                  _('Unable to retrieve user list.'))

            post = self.workflow.request.POST
            for role in roles:
                field = self.get_member_field_name(role.id)
                context[field] = post.getlist(field)
        return context


class CreateProject(workflows.Workflow):
    slug = "create_project"
    name = _("Create Project")
    finalize_button_name = _("Create Project")
    success_message = _('Created new project "%s".')
    failure_message = _('Unable to create project "%s".')
    success_url = "horizon:identity:project_admin:index"
    default_steps = (UpdateProjectMembers,)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        if PROJECT_GROUP_ENABLED:
            self.default_steps = (UpdateProjectMembers,)
        super(CreateProject, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

    def format_status_message(self, message):
        return message % self.context.get('name', 'unknown project')

    def _create_project(self, request, data):
        # create the project
        domain_id = data['domain_id']
        try:
            desc = data['description']
            self.object = api.keystone.tenant_create(request,
                                                     name=data['name'],
                                                     description=desc,
                                                     enabled=data['enabled'],
                                                     domain=domain_id)
            return self.object
        except Exception:
            exceptions.handle(request, ignore=True)
            return

    def _update_project_members(self, request, data, project_id):
        # update project members
        users_to_add = 0
        try:
            available_roles = api.keystone.role_list(request)
            member_step = self.get_step(PROJECT_USER_MEMBER_SLUG)
            # count how many users are to be added
            for role in available_roles:
                field_name = member_step.get_member_field_name(role.id)
                role_list = set(data[field_name])
                users_to_add += len(role_list)
            # add new users to project
            for role in available_roles:
                field_name = member_step.get_member_field_name(role.id)
                role_list = set(data[field_name])
                users_added = 0
                for user in role_list:
                    api.keystone.add_tenant_user_role(request,
                                                      project=project_id,
                                                      user=user,
                                                      role=role.id)
                    users_added += 1
                users_to_add -= users_added
        except Exception:
            if PROJECT_GROUP_ENABLED:
                group_msg = _(", add project groups")
            else:
                group_msg = ""
            exceptions.handle(request,
                              _('Failed to add %(users_to_add)s project '
                                'members%(group_msg)s and set project quotas.')
                              % {'users_to_add': users_to_add,
                                 'group_msg': group_msg})
        finally:
            auth_utils.remove_project_cache(request.user.token.id)

    def handle(self, request, data):
        project = self._create_project(request, data)
        if not project:
            return False
        project_id = project.id
        self._update_project_members(request, data, project_id)
        return True


class UpdateProjectInfoAction(CreateProjectInfoAction):
    enabled = forms.BooleanField(required=False, label=_("Enabled"))

    def __init__(self, request, initial, *args, **kwargs):
        super(UpdateProjectInfoAction, self).__init__(
            request, initial, *args, **kwargs)
        if initial['project_id'] == request.user.token.project['id']:
            self.fields['enabled'].widget.attrs['disabled'] = True
            self.fields['enabled'].help_text = _(
                'You cannot disable your current project')

    def clean(self):
        cleaned_data = super(UpdateProjectInfoAction, self).clean()
        # NOTE(tsufiev): in case the current project is being edited, its
        # 'enabled' field is disabled to prevent changing the field value
        # which is always `True` for the current project (because the user
        # logged in it). Since Django treats disabled checkbox as providing
        # `False` value even if its initial value is `True`, we need to
        # restore the original `True` value of 'enabled' field here.
        if self.fields['enabled'].widget.attrs.get('disabled', False):
            cleaned_data['enabled'] = True
        return cleaned_data

    class Meta(object):
        name = _("Project Information")
        slug = 'update_info'
        help_text = _("Edit the project details.")


class UpdateProjectInfo(workflows.Step):
    action_class = UpdateProjectInfoAction
    template_name = COMMON_HORIZONTAL_TEMPLATE
    depends_on = ("project_id",)
    contributes = ("domain_id",
                   "domain_name",
                   "name",
                   "description",
                   "enabled")


class UpdateProject(workflows.Workflow):
    slug = "update_project"
    name = _("Edit Project")
    finalize_button_name = _("Save")
    success_message = _('Modified project "%s".')
    failure_message = _('Unable to modify project "%s".')
    success_url = "horizon:identity:project_admin:index"
    default_steps = (UpdateProjectMembers,)

    def __init__(self, request=None, context_seed=None, entry_point=None,
                 *args, **kwargs):
        if PROJECT_GROUP_ENABLED:
            self.default_steps = (UpdateProjectMembers,)

        super(UpdateProject, self).__init__(request=request,
                                            context_seed=context_seed,
                                            entry_point=entry_point,
                                            *args,
                                            **kwargs)

    def format_status_message(self, message):
        return message % self.context.get('name', 'unknown project')

    @memoized.memoized_method
    def _get_available_roles(self, request):
        return api.keystone.role_list(request)

    def _update_project(self, request, data):
        # update project info
        try:
            project_id = data['project_id']
            return api.keystone.tenant_update(
                request,
                project_id,
                name=data['name'],
                description=data['description'],
                enabled=data['enabled'])
        except Exception:
            exceptions.handle(request, ignore=True)
            return

    def _add_roles_to_users(self, request, data, project_id, user_id,
                            role_ids, available_roles):
        member_step = self.get_step(PROJECT_USER_MEMBER_SLUG)
        current_role_ids = list(role_ids)

        for role in available_roles:
            field_name = member_step.get_member_field_name(role.id)
            # Check if the user is in the list of users with this role.
            if user_id in data[field_name]:
                # Add it if necessary
                if role.id not in current_role_ids:
                    # user role has changed
                    api.keystone.add_tenant_user_role(
                        request,
                        project=project_id,
                        user=user_id,
                        role=role.id)
                else:
                    # User role is unchanged, so remove it from the
                    # remaining roles list to avoid removing it later.
                    index = current_role_ids.index(role.id)
                    current_role_ids.pop(index)
        return current_role_ids

    def _remove_roles_from_user(self, request, project_id, user_id,
                                current_role_ids):
        for id_to_delete in current_role_ids:
            api.keystone.remove_tenant_user_role(
                request,
                project=project_id,
                user=user_id,
                role=id_to_delete)

    def _is_removing_self_admin_role(self, request, project_id, user_id,
                                     available_roles, current_role_ids):
        is_current_user = user_id == request.user.id
        is_current_project = project_id == request.user.tenant_id
        available_admin_role_ids = [role.id for role in available_roles
                                    if role.name.lower() == 'admin']
        admin_roles = [role for role in current_role_ids
                       if role in available_admin_role_ids]
        if len(admin_roles):
            removing_admin = any([role in current_role_ids
                                  for role in admin_roles])
        else:
            removing_admin = False

        if is_current_user and is_current_project and removing_admin:
            # Cannot remove "admin" role on current(admin) project
            msg = _('You cannot revoke your administrative privileges '
                    'from the project you are currently logged into. '
                    'Please switch to another project with '
                    'administrative privileges or remove the '
                    'administrative role manually via the CLI.')
            messages.warning(request, msg)
            return True
        else:
            return False

    def _update_project_members(self, request, data, project_id):
        # update project members
        users_to_modify = 0
        # Project-user member step
        member_step = self.get_step(PROJECT_USER_MEMBER_SLUG)
        try:
            # Get our role options
            available_roles = self._get_available_roles(request)
            # Get the users currently associated with this project so we
            # can diff against it.
            users_roles = api.keystone.get_project_users_roles(
                request, project=project_id)
            users_to_modify = len(users_roles)

            for user_id in users_roles.keys():
                # Check if there have been any changes in the roles of
                # Existing project members.
                current_role_ids = list(users_roles[user_id])
                modified_role_ids = self._add_roles_to_users(
                    request, data, project_id, user_id,
                    current_role_ids, available_roles)
                # Prevent admins from doing stupid things to themselves.
                removing_admin = self._is_removing_self_admin_role(
                    request, project_id, user_id, available_roles,
                    modified_role_ids)
                # Otherwise go through and revoke any removed roles.
                if not removing_admin:
                    self._remove_roles_from_user(request, project_id, user_id,
                                                 modified_role_ids)
                users_to_modify -= 1

            # Grant new roles on the project.
            for role in available_roles:
                field_name = member_step.get_member_field_name(role.id)
                # Count how many users may be added for exception handling.
                users_to_modify += len(set(data[field_name]))
            for role in available_roles:
                users_added = 0
                field_name = member_step.get_member_field_name(role.id)
                for user_id in set(data[field_name]):
                    if user_id not in users_roles:
                        api.keystone.add_tenant_user_role(request,
                                                          project=project_id,
                                                          user=user_id,
                                                          role=role.id)
                    users_added += 1
                users_to_modify -= users_added
            return True
        except Exception:
            if PROJECT_GROUP_ENABLED:
                group_msg = _(", update project groups")
            else:
                group_msg = ""
            exceptions.handle(request,
                              _('Failed to modify %(users_to_modify)s'
                                ' project members%(group_msg)s and '
                                'update project quotas.')
                              % {'users_to_modify': users_to_modify,
                                 'group_msg': group_msg})
            return False
        finally:
            auth_utils.remove_project_cache(request.user.token.id)

    def handle(self, request, data):
        # FIXME(gabriel): This should be refactored to use Python's built-in
        # sets and do this all in a single "roles to add" and "roles to remove"
        # pass instead of the multi-pass thing happening now.

        project_id = data['project_id']

        ret = self._update_project_members(request, data, project_id)
        if not ret:
            return False

        return True
