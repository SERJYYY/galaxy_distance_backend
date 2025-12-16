from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Galaxy, GalaxyRequest, GalaxiesInRequest, CustomUser

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
    list_display = ("id", "galaxy_request", "galaxy", "magnitude", "distance", "added_at")
    list_filter = ("galaxy_request__status",)
    search_fields = ("galaxy__name",)


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'is_active')
    list_filter = ('is_staff', 'is_superuser', 'is_active')
    search_fields = ('username', 'email')
    ordering = ('username',)
    
    # формы редактирования и создания пользователя
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личная информация', {'fields': ('first_name', 'last_name', 'email')}),
        ('Права', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Важные даты', {'fields': ('last_login',)}),  # убрал date_joined
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'is_active', 'is_staff', 'is_superuser')}
        ),
    )
