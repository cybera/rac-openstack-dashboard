from django import conf
from django.utils.translation import ugettext_lazy as _
from horizon import tabs

from openstack_dashboard import api

import requests

class RACProjectUsageTab(tabs.Tab):
    name = "Project Usage"
    slug = "project"
    template_name = "project/rac_usage/project_usage.html"
    preload = False

    def get_context_data(self, request):
        context = {}
        time = [
            ('7 Days', '7d'),
            ('14 Days', '14d'),
            ('30 Days', '30d'),
            ('90 Days', '90d'),
        ]
        queries = [
            ('Instances', 'project_allocated_instances'),
            ('CPU', 'project_allocated_cpu'),
            ('Memory (gb)', 'project_allocated_memory'),
            ('Ephemeral Disk (gb)', 'project_allocated_ephemeral_disk')
        ]

        context['time'] = time
        context['queries'] = queries
        context['request'] = self.request
        return context

class RACInstanceUsageTab(tabs.Tab):
    name = "Instance Usage"
    slug = "instances"
    template_name = "project/rac_usage/instance_usage.html"
    preload = False

    def get_context_data(self, request):
        instances, foo = api.nova.server_list(self.request)

        context = {}
        time = [
            ('7 Days', '7d'),
            ('14 Days', '14d'),
            ('30 Days', '30d'),
            ('90 Days', '90d'),
        ]
        queries = [
            ('CPU Time (Seconds)', 'instance_actual_cpu_time'),
            ('Memory Usage', 'instance_actual_memory'),
            ('Network (Bytes)', 'instance_actual_network_bytes'),
            ('Disk Usage', 'instance_actual_disk_usage'),
            ('Disk IO', 'instance_actual_disk_io'),
        ]
        context['time'] = time
        context['queries'] = queries
        context['request'] = self.request
        context['instances'] = instances
        return context

class RACUsageTabs(tabs.TabGroup):
    slug = "rac_usage"
    tabs = (RACProjectUsageTab,RACInstanceUsageTab)
