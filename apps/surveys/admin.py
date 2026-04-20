from django.contrib import admin

from apps.surveys.models import Field, FieldCondition, FieldOption, Section, Survey


class SectionInline(admin.TabularInline):
    model = Section
    extra = 0


@admin.register(Survey)
class SurveyAdmin(admin.ModelAdmin):
    list_display = ["title", "owner", "status", "version", "created_at"]
    list_filter = ["status"]
    search_fields = ["title", "owner__email"]
    inlines = [SectionInline]


class FieldInline(admin.TabularInline):
    model = Field
    extra = 0


@admin.register(Section)
class SectionAdmin(admin.ModelAdmin):
    list_display = ["title", "survey", "order"]
    inlines = [FieldInline]


class FieldOptionInline(admin.TabularInline):
    model = FieldOption
    extra = 0


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ["label", "field_type", "section", "order", "is_required", "is_sensitive"]
    list_filter = ["field_type", "is_required", "is_sensitive"]
    inlines = [FieldOptionInline]


@admin.register(FieldOption)
class FieldOptionAdmin(admin.ModelAdmin):
    list_display = ["label", "value", "field", "order"]


@admin.register(FieldCondition)
class FieldConditionAdmin(admin.ModelAdmin):
    list_display = ["source_field", "operator", "expected_value", "target_field", "target_section"]
