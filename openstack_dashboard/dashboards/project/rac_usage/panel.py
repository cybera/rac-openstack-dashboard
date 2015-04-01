from django.utils.translation import ugettext_lazy as _
import horizon
from openstack_dashboard.dashboards.project import dashboard


class RACUsage(horizon.Panel):
    name = _("Usage Graphs")
    slug = 'rac_usage'

dashboard.Project.register(RACUsage)
