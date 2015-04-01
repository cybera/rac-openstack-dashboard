from django.conf.urls import patterns  # noqa
from django.conf.urls import url  # noqa

from openstack_dashboard.dashboards.project.rac_usage import views


urlpatterns = patterns('openstack_dashboard.dashboards.project.rac_usage.views',
    url(r'^$', views.RACUsageView.as_view(), name='index'),
    url(r'^index$', views.RACUsageView.as_view(), name='index'),
    url(r'^project_data$', views.RACProjectData.as_view(), name='project_data'),
    url(r'^instance_data$', views.RACInstanceData.as_view(), name='instance_data'),
    url(r'^warning$', views.WarningView.as_view(), name='warning'),
)
