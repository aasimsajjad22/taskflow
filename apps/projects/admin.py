from django.contrib import admin

from .models import Comment, Project, Task


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    # Columns in the list.
    list_display = ["key", "name", "workspace", "is_archived", "created_at"]
    # Filter sidebar.
    list_filter = ["is_archived", "workspace"]
    # Search box.
    search_fields = ["name", "key"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    # Columns in the list.
    list_display = ["title", "project", "status", "priority", "assignee", "due_date"]
    # Filter sidebar.
    list_filter = ["status", "priority", "project"]
    # Search box.
    search_fields = ["title", "description"]
    # JOIN these tables on the list page to avoid N+1 queries.
    list_select_related = ["project", "assignee"]


# Admin settings for Comment.
@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    # Columns in the list.
    list_display = ["task", "author", "created_at"]
    # Search box.
    search_fields = ["body"]
