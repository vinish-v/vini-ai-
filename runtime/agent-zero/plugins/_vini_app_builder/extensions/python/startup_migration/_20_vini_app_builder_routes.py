from __future__ import annotations

from helpers.extension import Extension
from plugins._vini_app_builder.helpers.route_bootstrap import install_route_hooks


class ViniAppBuilderRoutesStartup(Extension):
    def execute(self, **kwargs):
        install_route_hooks()
