from django.core.cache import cache

from apps.surveys.models import Field, FieldCondition, FieldOption, Section, Survey

SURVEY_DETAIL_TTL = 60 * 10  # 10 minutes


def _cache_key(survey_id) -> str:
    """Return the Redis cache key for a survey's detail data."""
    return f"survey:{survey_id}:detail"


def invalidate_survey_cache(survey_id) -> None:
    """Remove the cached detail entry for a survey, forcing the next read to hit the DB."""
    cache.delete(_cache_key(survey_id))


# ---------------------------------------------------------------------------
# Survey CRUD
# ---------------------------------------------------------------------------

def create_survey(data: dict, user) -> Survey:
    """Create and return a new Survey owned by *user*."""
    return Survey.objects.create(owner=user, **data)


def get_survey_list(user=None):
    """Return all surveys. Optionally filter to a specific owner."""
    qs = Survey.objects.select_related("owner")
    if user is not None:
        qs = qs.filter(owner=user)
    return qs


def get_survey_by_id(survey_id: str) -> Survey | None:
    """Fetch a single Survey by primary key; returns None if not found."""
    try:
        return Survey.objects.select_related("owner").get(pk=survey_id)
    except Survey.DoesNotExist:
        return None


def get_survey_detail_cached(survey_id: str) -> Survey | None:
    """Return a Survey, pulling from Redis cache when available."""
    key = _cache_key(survey_id)
    cached_pk = cache.get(key)

    if cached_pk is not None:
        try:
            return Survey.objects.select_related("owner").prefetch_related(
                "sections__fields__options",
                "sections__fields__conditions_as_source",
            ).get(pk=cached_pk)
        except Survey.DoesNotExist:
            cache.delete(key)

    survey = Survey.objects.select_related("owner").prefetch_related(
        "sections__fields__options",
        "sections__fields__conditions_as_source",
    ).filter(pk=survey_id).first()

    if survey is not None:
        cache.set(key, str(survey.pk), SURVEY_DETAIL_TTL)
    return survey


def update_survey(survey: Survey, data: dict) -> Survey:
    """Apply *data* fields to *survey*, persist, and invalidate its cache entry."""
    for field, value in data.items():
        setattr(survey, field, value)
    survey.save()
    invalidate_survey_cache(survey.pk)
    return survey


def delete_survey(survey: Survey) -> None:
    """Delete *survey* from the database and remove its cache entry."""
    survey_id = survey.pk
    survey.delete()
    invalidate_survey_cache(survey_id)


def publish_survey(survey: Survey) -> Survey:
    """Transition *survey* from DRAFT to PUBLISHED. Raises ValueError if not in draft state."""
    if survey.status != Survey.Status.DRAFT:
        raise ValueError("Only draft surveys can be published.")
    survey.status = Survey.Status.PUBLISHED
    survey.save(update_fields=["status", "updated_at"])
    invalidate_survey_cache(survey.pk)
    return survey


def clone_survey(survey: Survey, user) -> Survey:
    """Deep-clone a survey: copies sections, fields, and options into a new draft."""
    new_survey = Survey.objects.create(
        title=f"Copy of {survey.title}",
        description=survey.description,
        owner=user,
        status=Survey.Status.DRAFT,
        version=1,
        is_anonymous=survey.is_anonymous,
        requires_auth=survey.requires_auth,
    )

    for section in survey.sections.order_by("order"):
        new_section = Section.objects.create(
            survey=new_survey,
            title=section.title,
            order=section.order,
            # Conditions reference specific field PKs; skip re-wiring in clone.
        )
        for field in section.fields.order_by("order"):
            new_field = Field.objects.create(
                section=new_section,
                label=field.label,
                field_type=field.field_type,
                is_required=field.is_required,
                order=field.order,
                is_sensitive=field.is_sensitive,
                placeholder=field.placeholder,
                help_text=field.help_text,
                config=field.config,
            )
            for option in field.options.order_by("order"):
                FieldOption.objects.create(
                    field=new_field,
                    label=option.label,
                    value=option.value,
                    order=option.order,
                )

    return new_survey


# ---------------------------------------------------------------------------
# Section CRUD
# ---------------------------------------------------------------------------

def get_sections(survey: Survey):
    """Return all sections belonging to *survey*, ordered by the DB default."""
    return survey.sections.all()


def create_section(survey: Survey, data: dict) -> Section:
    """Create a new Section inside *survey* and invalidate the survey cache."""
    section = Section.objects.create(survey=survey, **data)
    invalidate_survey_cache(survey.pk)
    return section


def get_section_by_id(survey: Survey, section_id: str) -> Section | None:
    """Return a Section scoped to *survey* by primary key; None if not found."""
    try:
        return survey.sections.get(pk=section_id)
    except Section.DoesNotExist:
        return None


def update_section(section: Section, data: dict) -> Section:
    """Apply *data* fields to *section*, persist, and invalidate the parent survey cache."""
    for field, value in data.items():
        setattr(section, field, value)
    section.save()
    invalidate_survey_cache(section.survey_id)
    return section


def delete_section(section: Section) -> None:
    """Delete *section* and invalidate the parent survey cache."""
    survey_id = section.survey_id
    section.delete()
    invalidate_survey_cache(survey_id)


# ---------------------------------------------------------------------------
# Field CRUD
# ---------------------------------------------------------------------------

def get_fields(section: Section):
    """Return all fields in *section*, prefetching related options."""
    return section.fields.prefetch_related("options").all()


def create_field(section: Section, data: dict) -> Field:
    """Create a new Field inside *section* and invalidate the parent survey cache."""
    field = Field.objects.create(section=section, **data)
    invalidate_survey_cache(section.survey_id)
    return field


def get_field_by_id(section: Section, field_id: str) -> Field | None:
    """Return a Field scoped to *section* by primary key; None if not found."""
    try:
        return section.fields.get(pk=field_id)
    except Field.DoesNotExist:
        return None


def update_field(field: Field, data: dict) -> Field:
    """Apply *data* attributes to *field*, persist, and invalidate the parent survey cache."""
    for attr, value in data.items():
        setattr(field, attr, value)
    field.save()
    invalidate_survey_cache(field.section.survey_id)
    return field


def delete_field(field: Field) -> None:
    """Delete *field* and invalidate the parent survey cache."""
    survey_id = field.section.survey_id
    field.delete()
    invalidate_survey_cache(survey_id)


# ---------------------------------------------------------------------------
# Condition CRUD
# ---------------------------------------------------------------------------

def create_condition(source_field: Field, data: dict) -> FieldCondition:
    """Create a FieldCondition on *source_field* and invalidate the parent survey cache."""
    condition = FieldCondition.objects.create(source_field=source_field, **data)
    invalidate_survey_cache(source_field.section.survey_id)
    return condition


def get_condition_by_id(condition_id: str) -> FieldCondition | None:
    """Return a FieldCondition by primary key with its survey chain pre-selected; None if not found."""
    try:
        return FieldCondition.objects.select_related(
            "source_field__section__survey"
        ).get(pk=condition_id)
    except FieldCondition.DoesNotExist:
        return None


def delete_condition(condition: FieldCondition) -> None:
    """Delete *condition* and invalidate the parent survey cache."""
    survey_id = condition.source_field.section.survey_id
    condition.delete()
    invalidate_survey_cache(survey_id)
