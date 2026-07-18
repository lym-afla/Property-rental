"""DRF permissions for the rentals API (Task 16)."""

from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsOwnerOrReadOnly(BasePermission):
    """Object-level permission: only the owning landlord may mutate.

    Models in this app reach the owning ``User`` via two routes:

    * ``Property`` exposes the owner directly as ``obj.owned_by.user``.
    * Every other user-facing model (``Tenant``, ``Transaction``,
      ``Property_capital_structure``) reaches the owner through its
      ``property`` FK: ``obj.property.owned_by.user``.

    This permission handles both shapes by inspecting the object. Safe
    methods (GET/HEAD/OPTIONS) still require the requester to be the
    owner (the app's data is private to each landlord), matching the
    behavior the existing template views already enforce inline.
    """

    def has_object_permission(self, request, view, obj):
        owner_user = self._owner_user(obj)
        if owner_user is None:
            # Defensive default: if we cannot resolve an owner, deny.
            return False
        if request.method in SAFE_METHODS:
            return owner_user == request.user
        return owner_user == request.user

    @staticmethod
    def _owner_user(obj):
        """Resolve the owning ``User`` for either model shape.

        Returns ``None`` if neither attribute path exists.
        """
        # Property: ``obj.owned_by.user``
        owned_by = getattr(obj, "owned_by", None)
        if owned_by is not None:
            return getattr(owned_by, "user", None)
        # Sub-resource: ``obj.property.owned_by.user``
        property_obj = getattr(obj, "property", None)
        if property_obj is not None:
            return getattr(getattr(property_obj, "owned_by", None), "user", None)
        return None
