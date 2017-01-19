from django.template.defaultfilters import capfirst  # noqa
from django.template.defaultfilters import floatformat  # noqa
from django.utils.translation import ugettext_lazy as _
from django.views.generic import TemplateView  # noqa
from django import http

from horizon.utils import csvbase
from horizon import tabs

from openstack_dashboard import api

from .tabs import RACUsageTabs
import requests

class RACUsageView(tabs.TabView):
    tab_group_class = RACUsageTabs
    template_name = 'project/rac_usage/index.html'

    def get(self, request, *args, **kwargs):
        return super(RACUsageView, self).get(request, *args, **kwargs)

class RACProjectData(TemplateView):
    def get(self, request, *args, **kwargs):
        from_date = self.request.GET.get('from', '7d')
        project_id = self.request.user.tenant_id
        data_format = self.request.GET.get('format', False)
        base_url = 'http://yyc-graphite.cloud.cybera.ca/render?from=-%s&width=800&format=%s&target=' % (from_date, data_format)
        query_results = {}
        queries = {
            'project_allocated_instances': "aliasByNode(keepLastValue(projects.%s.cloud_usage.*.instances), 3)" % project_id,
            'project_allocated_cpu': "aliasByNode(keepLastValue(projects.%s.cloud_usage.*.cpu), 3)" % project_id,
            'project_allocated_memory': "aliasByNode(keepLastValue(projects.%s.cloud_usage.*.memory), 3)" % project_id,
            'project_allocated_ephemeral_disk': "aliasByNode(keepLastValue(projects.%s.cloud_usage.*.disk), 3)" % project_id,
        }

        query = self.request.GET.get('query', False)
        if query:
            r = requests.get("%s%s" % (base_url, queries[query]))
            return http.HttpResponse(r.content)

class RACInstanceData(TemplateView):
    def get(self, request, *args, **kwargs):
        from_date = self.request.GET.get('from', '7d')

        instance_id = self.request.GET.get('instance', False)
        instances, foo = api.nova.server_list(self.request)
        if len([x for x in instances if x.id == instance_id]) == 0:
            return None

        data_format = self.request.GET.get('format', False)
        if data_format not in ['csv', 'json', False]:
            return None

        project_id = self.request.user.tenant_id
        base_url = 'http://yyc-graphite.cloud.cybera.ca/render?from=-%s&width=800&format=%s&target=' % (from_date, data_format)
        query_results = {}
        queries = {
            'instance_actual_cpu_time': "aliasByNode(derivative(summarize(projects.%s.instances.%s.cpu.cpu_time, '10min', 'avg')), 5)" % (project_id, instance_id),
            'instance_actual_memory': "aliasByNode(scale(projects.%s.instances.%s.memory.available, 1024), 5)&target=aliasByNode(scale(projects.%s.instances.%s.memory.used,1024),5)&yMin=0" % (project_id, instance_id, project_id, instance_id),
            'instance_actual_network_bytes': "aliasByNode(derivative(summarize(projects.%s.instances.%s.interface.eth0.rx_bytes, '10min', 'max')), 6)&target=aliasByNode(derivative(summarize(projects.%s.instances.%s.interface.eth0.tx_bytes,'10min','max')),6)&yMin=0" % (project_id, instance_id, project_id, instance_id),
            'instance_actual_disk_usage': "aliasByNode(projects.%s.instances.%s.disk.vda.bytes_used,6)&yMin=0" % (project_id, instance_id),
            'instance_actual_disk_io': "aliasByNode(derivative(summarize(projects.%s.instances.%s.disk.vda.wr_req,'10min','avg')),6)&target=aliasByNode(derivative(summarize(projects.%s.instances.%s.disk.vda.rd_req,'10min','avg')), 6)&yMin=0" % (project_id, instance_id, project_id, instance_id),
        }

        query = self.request.GET.get('query', False)
        if query:
            r = requests.get("%s%s" % (base_url, queries[query]))
            return http.HttpResponse(r.content)


class WarningView(TemplateView):
    template_name = "project/_warning.html"
