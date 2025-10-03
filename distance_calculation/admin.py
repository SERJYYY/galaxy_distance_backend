from django.contrib import admin
from .models import Galaxy, GalaxyRequest, GalaxiesInRequest

# Inline для связи "галактики в заявке"
class GalaxiesInRequestInline(admin.TabularInline):
    model = GalaxiesInRequest
    extra = 1


# Админка для галактик
@admin.register(Galaxy)
class GalaxyAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active",)


# Админка для заявок
@admin.register(GalaxyRequest)
class GalaxyRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "status", "created_at", "creator", "telescope")
    list_filter = ("status", "telescope")
    search_fields = ("creator__username", "telescope")
    inlines = [GalaxiesInRequestInline]


# Админка для промежуточной таблицы
@admin.register(GalaxiesInRequest)
class GalaxiesInRequestAdmin(admin.ModelAdmin):
    list_display = ("id", "galaxy_request", "galaxy", "magnitude", "distance")
    list_filter = ("galaxy_request__status",)
    search_fields = ("galaxy__name",)
