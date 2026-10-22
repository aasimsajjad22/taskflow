import django_filters

from .models import Task


class TaskFilter(django_filters.FilterSet):
    due_before = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    due_after = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")

    # ?overdue=true -> calls filter_overdue() below.
    # method="..." means: "don't build the filter yourself, call my method".
    overdue = django_filters.BooleanFilter(method="filter_overdue")
    # ?completed_late=true -> done after the due date.
    completed_late = django_filters.BooleanFilter(method="filter_completed_late")
    # ?unassigned=true -> no assignee.
    unassigned = django_filters.BooleanFilter(method="filter_unassigned")
    # ?assigned_to_me=true -> assigned to the logged-in user.
    assigned_to_me = django_filters.BooleanFilter(method="filter_assigned_to_me")

    class Meta:
        model = Task

        fields = ["project", "status", "priority", "assignee"]

    # django-filter calls this with: the queryset so far, the filter's name, and the value
    # (already converted to True/False). We only act on "true"; "false" changes nothing.
    def filter_overdue(self, queryset, name, value):
        # queryset is a TaskQuerySet, so our .overdue() scope is available.
        return queryset.overdue() if value else queryset

    # ?completed_late=true
    def filter_completed_late(self, queryset, name, value):
        return queryset.completed_late() if value else queryset

    # ?unassigned=true
    def filter_unassigned(self, queryset, name, value):
        return queryset.unassigned() if value else queryset

    # ?assigned_to_me=true
    def filter_assigned_to_me(self, queryset, name, value):
        # self.request is the current request. DRF's filter backend passes it in.
        return queryset.filter(assignee=self.request.user) if value else queryset
