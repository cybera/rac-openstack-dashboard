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

from django.core.urlresolvers import reverse
from django.utils.translation import ugettext_lazy as _
from django.views import generic

from horizon import exceptions
from horizon import messages
from horizon import tables
from horizon.utils import memoized
from horizon import workflows

from openstack_dashboard import api
from openstack_dashboard.api import keystone
from openstack_dashboard import policy
from openstack_dashboard import usage
from openstack_dashboard.usage import quotas

from openstack_dashboard.dashboards.identity.project_admin \
    import tables as project_tables
from openstack_dashboard.dashboards.identity.project_admin \
    import workflows as project_workflows
from openstack_dashboard.dashboards.identity.project_admin \
    import keystone as keystone_api
from openstack_dashboard.dashboards.project.overview \
    import views as project_views

PROJECT_INFO_FIELDS = ("domain_id",
                       "domain_name",
                       "name",
                       "description",
                       "enabled")

INDEX_URL = "horizon:identity:project_admin:index"


class TenantContextMixin(object):
    @memoized.memoized_method
    def get_object(self):
        tenant_id = self.kwargs['tenant_id']
        try:
            return api.keystone.tenant_get(self.request, tenant_id, admin=True)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project information.'),
                              redirect=reverse(INDEX_URL))

    def get_context_data(self, **kwargs):
        context = super(TenantContextMixin, self).get_context_data(**kwargs)
        context['tenant'] = self.get_object()
        return context


class IndexView(tables.DataTableView):
    table_class = project_tables.TenantsTable
    template_name = 'identity/projects/index.html'
    page_title = _("Projects")

    def has_more_data(self, table):
        return self._more

    def get_data(self):
        tenants = []
        marker = self.request.GET.get(
            project_tables.TenantsTable._meta.pagination_param, None)
        domain_context = self.request.session.get('domain_context', None)
        self._more = False
        if policy.check((("identity", "identity:list_user_projects"),),
                          self.request):
            try:
                user_tenants, self._more = api.keystone.tenant_list(
                    self.request,
                    user=self.request.user.id,
                    paginate=True,
                    marker=marker,
                    admin=False)

                for t in user_tenants:
                    try:
                        roles = keystone_api.roles_for_user(self.request, self.request.user.id, project=t.id)
                        for r in roles:
                            if r.name == 'Project Admin':
                                tenants.append(t)
                    except Exception:
                        pass
            except Exception:
                exceptions.handle(self.request,
                                  _("Unable to retrieve project information."))
        else:
            msg = \
                _("Insufficient privilege level to view project information.")
            messages.info(self.request, msg)
        return tenants


class ProjectUsageView(usage.UsageView):
    table_class = usage.ProjectUsageTable
    usage_class = usage.ProjectUsage
    template_name = 'identity/projects/usage.html'
    csv_response_class = project_views.ProjectUsageCsvRenderer
    csv_template_name = 'project/overview/usage.csv'
    page_title = _("Project Usage")

    def get_data(self):
        super(ProjectUsageView, self).get_data()
        return self.usage.get_instances()


class UpdateProjectView(workflows.WorkflowView):
    workflow_class = project_workflows.UpdateProject

    def get_initial(self):
        initial = super(UpdateProjectView, self).get_initial()

        project_id = self.kwargs['tenant_id']
        initial['project_id'] = project_id

        return initial


class DetailProjectView(generic.TemplateView):
    template_name = 'identity/projects/detail.html'

    def get_context_data(self, **kwargs):
        context = super(DetailProjectView, self).get_context_data(**kwargs)
        project = self.get_data()
        table = project_tables.TenantsTable(self.request)
        context["project"] = project
        context["page_title"] = _("Project Details: %s") % project.name
        context["url"] = reverse(INDEX_URL)
        context["actions"] = table.render_row_actions(project)
        return context

    @memoized.memoized_method
    def get_data(self):
        try:
            project_id = self.kwargs['project_id']
            project = api.keystone.tenant_get(self.request, project_id)
        except Exception:
            exceptions.handle(self.request,
                              _('Unable to retrieve project details.'),
                              redirect=reverse(INDEX_URL))
        return project
