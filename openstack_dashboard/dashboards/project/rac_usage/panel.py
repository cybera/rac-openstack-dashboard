from django.utils.translation import ugettext_lazy as _

import horizon


class RACUsage(horizon.Panel):
    name = _("Usage Graphs")
    slug = 'rac_usage'
