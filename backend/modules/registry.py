from flask import Blueprint


class ModuleRegistry:
    """Registro centralizado de módulos.

    Cada módulo se registra con un nombre único, un Blueprint y los roles
    que tienen acceso a él. Agregar un nuevo módulo solo requiere añadirlo aquí
    y crear su carpeta en backend/modules/<nombre>/.
    """

    def __init__(self):
        self._modules = {}

    def register(self, name, blueprint, label, icon, roles_allowed, sidebar_visible=True):
        self._modules[name] = {
            "blueprint": blueprint,
            "label": label,
            "icon": icon,
            "roles_allowed": roles_allowed,
            "sidebar_visible": sidebar_visible,
        }

    def get_module(self, name):
        return self._modules.get(name)

    def get_sidebar_items(self, role):
        items = []
        for mod in self._modules.values():
            if mod["sidebar_visible"] and (role in mod["roles_allowed"] or "*" in mod["roles_allowed"]):
                bp = mod["blueprint"]
                url = bp.url_prefix + "/" if bp.url_prefix else "/" + mod["blueprint"].name + "/"
                items.append({
                    "name": bp.name,
                    "label": mod["label"],
                    "icon": mod["icon"],
                    "url": url,
                })
        return items

    def register_blueprints(self, app):
        for mod in self._modules.values():
            app.register_blueprint(mod["blueprint"])

    def route(self, name):
        mod = self._modules.get(name)
        if mod:
            bp = mod["blueprint"]
            def decorator(f):
                return bp.route("/")(f)
            return decorator
        return None


module_registry = ModuleRegistry()