# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from django.utils.translation import ugettext_lazy as _

import horizon

from openstack_dashboard.dashboards.identity import dashboard

from openstack_dashboard.dashboards.identity.project_admin \
    import keystone as keystone_api


class ProjectAdmin(horizon.Panel):
    name = _("Project Administration")
    slug = 'project_admin'

    def allowed(self, context):
        request = context['request']
        user = request.user
        tenants = keystone_api.tenant_list(request, user=user, admin=False)[0]

        for t in tenants:
            try:
                roles = keystone_api.roles_for_user(request, user, project=t.id)
                for r in roles:
                    if r.name == 'Project Admin':
                        return True
            except Exception:
                pass

        return False


dashboard.Identity.register(ProjectAdmin)
