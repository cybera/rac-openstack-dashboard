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

from openstack_dashboard import api

from openstack_dashboard.dashboards.identity import dashboard


class ProjectAdmin(horizon.Panel):
    name = _("Project Administration")
    slug = 'project_admin'
    #policy_rules = (("identity", "identity:list_user_projects"))

    def allowed(self, context):
        request = context['request']
        user = request.user
        tenants = api.keystone.tenant_list(request, user=user, admin=False)

        for t in tenants:
           roles = api.keystone.roles_for_user(request, user, project=t)
           for r in roles:
               if r.name == 'Project Admin':
                   return True

        return False


dashboard.Identity.register(ProjectAdmin)
