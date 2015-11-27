from openstack_dashboard.api import swift
import requests
import json

def get_swift_quota(request):
    head = swift.swift_api(request).head_account()
    if 'x-account-meta-quota-bytes' in head:
        return int(head['x-account-meta-quota-bytes']) / 1024 / 1024
    return 1048576

def get_swift_usage(request):
    project_id = request.user.tenant_id
    base_url = 'http://yyc-graphite.cloud.cybera.ca/render?from=-7d&width=800&format=json&target='
    query_results = {}
    quota_query = "aliasByNode(smartSummarize(sumSeries(swift.*.project.%s.account_size), '1h', 'sum'), 4)" % project_id

    r = requests.get("%s%s" % (base_url, quota_query))
    result = json.loads(r.content)
    if len(result) >= 1 and 'datapoints' in result[0]:
        usage = int(result[0]['datapoints'][-2][0])
        if usage > 0:
            return usage / 1024 / 1024
    return 0
