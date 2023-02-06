import logging
from django.urls import resolve

logger = logging.getLogger(__name__)


class StepsHelper:
    """
    Helps with form steps in a form wizard.

    Code adapted from
    https://github.com/jazzband/django-formtools/blob/master/formtools/wizard/views.py

    LICENSE FOR THIS CLASS

    Copyright (c) Django Software Foundation and individual contributors.

    All rights reserved.

    Redistribution and use in source and binary forms, with or without modification,
    are permitted provided that the following conditions are met:

        1. Redistributions of source code must retain the above copyright notice,
        this list of conditions and the following disclaimer.

        2. Redistributions in binary form must reproduce the above copyright
        notice, this list of conditions and the following disclaimer in the
        documentation and/or other materials provided with the distribution.

        3. Neither the name of django-formtools nor the names of its contributors
        may be used to endorse or promote products derived from this software
        without specific prior written permission.

    THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
    ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
    WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
    DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
    ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
    (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
    LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
    ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
    SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
    """

    def __init__(self, wizard):
        self._wizard = wizard

    def __dir__(self):
        return self.all

    def __len__(self):
        return self.count

    def __repr__(self):
        return "<StepsHelper for %s (steps: %s)>" % (self._wizard, self.all)

    def __getitem__(self, step):
        return self.all[step]

    @property
    def all(self):
        """Returns the names of all steps."""
        return self._wizard.get_step_list()

    @property
    def count(self):
        """Returns the total number of steps/forms in this the wizard."""
        return len(self.all)

    @property
    def current(self):
        """
        Returns the current step (a string). If no current step is stored in the
        storage backend, the first step will be returned.
        """
        step = getattr(self._wizard.storage, "current_step", None)
        if step is None:
            current_url = resolve(self._wizard.request.path_info).url_name
            step = current_url if current_url in self.all else self.first
            self._wizard.storage["current_step"] = step
        return step

    @current.setter
    def current(self, step: str):
        """Sets the current step. Updates step history."""
        if step in self.all:
            self._wizard.storage["current_step"] = step
        else:
            logger.debug("Invalid step name %s given to StepHelper" % str(step))
            self._wizard.storage["current_step"] = self.first

        # can't serialize a set, so keep list entries unique
        if step not in self.history:
            self.history.append(step)

    @property
    def first(self):
        """Returns the name of the first step."""
        return self.all[0]

    @property
    def last(self):
        """Returns the name of the last step."""
        return self.all[-1]

    @property
    def next(self):
        """Returns the next step."""
        steps = self.all
        index = steps.index(self.current) + 1
        if index < self.count:
            return steps[index]
        return None

    @property
    def prev(self):
        """Returns the previous step."""
        steps = self.all
        key = steps.index(self.current) - 1
        if key >= 0:
            return steps[key]
        return None

    @property
    def index(self):
        """Returns the index for the current step."""
        steps = self.all
        if self.current in steps:
            return steps.index(self)
        return None

    @property
    def history(self):
        """Returns the list of already visited steps."""
        return self._wizard.storage.setdefault("step_history", [])
