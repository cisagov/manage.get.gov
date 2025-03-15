from registrar.models.utility.time_stamped_model import TimeStampedModel
from registrar.utility.db_helpers import object_is_being_created
from django.core.exceptions import ValidationError


class StateControlledModel(TimeStampedModel):
    """
    An abstract base model that adds restrictions to Viewflow state controlled fields.
    This will prevent fields named Status or State from being changed manually.
    For example, object.state = SomeState would result in a immediate validation error

    Only use this when applying Viewflow FSM control to a model.
    Caveate - this class would need to be changed if there is ever a need to have both a state field and a status field in the same model
    """

    class Meta:
        abstract = True
        # don't put anything else here, it will be ignored

    def __setattr__(self, name, value):
        """Overrides the setter ('=' operator) with custom logic
        This will block anyone from setting the state/status field using the = operator
        The object can still be created for the first time with this field filled in.
        """

        if isinstance(self, StateControlledModel) and not object_is_being_created(self):
            if name == "status":
                raise ValidationError("Direct changes to 'status' are not allowed.")
            elif name == "state":
                raise ValidationError("Direct changes to 'state' are not allowed.")

        super().__setattr__(name, value)
