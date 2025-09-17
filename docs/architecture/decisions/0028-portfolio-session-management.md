# 28. Portfolio session management

Date: 2025-05-29

# Status

Approved

## Context

Django is built primarily to support static forms. To “dynamically” switch the active portfolio in session, we can handle this either by (1) passing in portfolio id into Django’s static forms or (2) rerouting the user to a URL path that handles switching the session portfolio.

## Considered Options

**[SELECTED] Option 1:** Submit a form that passes value of selected session portfolio
One big form that when selected, passes in the value of the selected button.
**Portfolio select organization form button - Django template**
```
<button
	type="submit"
	class="usa-card__container margin-left-0"
	name="set-session-portfolio-button"
	value="{{portfolio.id}}"
```

**Django view**
```
def post(self, request, *args, **kwargs):
"""
Handles updating active portfolio in session.
"""
# get_form handled by a Django Form class elsewhere
self.form = self.get_form()

	# grab portfolio ID from the id of the HTML button submitted
portfolio_id = self.form['set_session_portfolio_button'].value()

portfolio = get_object_or_404(Portfolio, pk=portfolio_id)
request.session["portfolio"] = portfolio

# Redirect to /domains
return self._handle_success_response(request, portfolio)
```

✅ Pros:
Allows us to fully set session portfolio within a view without relying on making and calling a URL path to change the session portfolio. This prevents the user’s ability to set an active session portfolio by calling the URL path on their own.   

❌ Cons:
Switching our session portfolio through the form requires switching through the HTML value passed into our form. This exposes our portfolio id’s since we are grabbing the portfolio value we want to select by data in our HTML form elements, which users can access through browser dev tools.

Alternative approaches: 
Pass in portfolio name as form value. Change the form input value to another identifying field of the portfolio that does not expose database information, for example the portfolio’s name. Recently we updated our registrar to have unique organization names, so this could be a working identifier that does not expose the id's and instead uses public info.


**Option 2:** Call a URL path that passes in id of selected session portfolio
We create a method (either in API views or a Django view) that handles switching the session portfolio by taking the id of the portfolio we want to switch to. That method is then added to our list of accessible paths in urls.py.

**urls.py**
```
path(
"set-session-portfolio/<int:object_pk>",
[view_method_location],
name="set-session-portfolio"
    ),

```

✅ Pros:
URL path that handles session portfolio management allows for reusability throughout app. Also may be the most straightforward as it doesn’t require creating a new form (in Option 2b)

This method may also possibly make it more straightforward to implement the organizations selector menu. We haven’t implemented this menu yet. On initial glance, it may be possible to also treat this menu as a Django form, but there are some concerns on if it makes sense to treat this menu as a form. 

❌ Cons:
There is a chance the URL we use to switch session portfolios may also be manually accessed by the user directly on their browser. 

## Decision
We will implement allowing users to manage the portfolio session by submitting a form (Option 1) that passes in the organization name. Because portfolios are expected to have unique organization names, we can use these values to manage session without exposing the portfolio’s id on the frontend. 
