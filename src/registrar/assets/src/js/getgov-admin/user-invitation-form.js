/**
 * Shared admin behavior for forms that select an existing user or invite a
 * new user by email. This is used by UserPortfolioPermission and
 * UserDomainRole forms.
 *
 * UserOrEmailAutocompleteSelect can submit either an existing user's ID or a
 * newly typed email address. The Select2 AJAX results can lag behind the live
 * search text, so this module commits the complete email before Enter, Tab,
 * or closing the control can use a stale result.
 */

function getOpenSelect2SearchInput() {
    return document.querySelector(".select2-container--open .select2-search__field");
}

function commitTypedEmail(userField, searchInput) {
    const email = searchInput?.value.trim();

    // This field has two modes: text without "@" is an autocomplete query for
    // an existing user; text with "@" is a free-text email to submit. Will not
    // turn an ordinary user search into a new option when the control closes.
    // This is not email validation, UserOrEmailChoiceField validates the value
    // in Django after it is submitted.
    if (!email || !email.includes("@")) {
        return false;
    }

    let option = Array.from(userField.options).find((candidate) => candidate.value === email);
    if (!option) {
        option = new Option(email, email, true, true);
        userField.add(option);
    }

    userField.value = email;
    django.jQuery(userField).trigger("change");
    return true;
}

function setUpUserOrEmailAutocomplete(userField) {
    if (!userField?.matches('[data-user-or-email-autocomplete="true"]')) {
        return;
    }

    const $userField = django.jQuery(userField);
    let boundSearchInput = null;
    let skipNextClose = false;

    $userField.on("select2:open", function() {
        const searchInput = getOpenSelect2SearchInput();
        if (!searchInput || searchInput === boundSearchInput) {
            return;
        }
        boundSearchInput = searchInput;

        // When user presses enter or tab, commit before Select2 uses a stale value from the AJAX results.
        // When user presses escape, skip the next close event.
        searchInput.addEventListener("keydown", function(event) {
            if (event.key === "Escape") {
                skipNextClose = true;
                return;
            }

            if (!["Enter", "Tab"].includes(event.key) || !commitTypedEmail(userField, searchInput)) {
                return;
            }

            event.stopImmediatePropagation();
            if (event.key === "Enter") {
                event.preventDefault();
            }
            $userField.select2("close");
        }, { capture: true });
    });

    // Keep a user explicitly selected from the AJAX results.
    $userField.on("select2:selecting", function() {
        skipNextClose = true;
    });

    // Commit the updated value when focus leaves the control or user clicks elsewhere.
    $userField.on("select2:closing", function() {
        if (skipNextClose) {
            skipNextClose = false;
            return;
        }
        commitTypedEmail(userField, getOpenSelect2SearchInput());
    });
}

function isSelectedUserIdValue(value) {
    if (!value) {
        return false;
    }
    return Number.isInteger(Number(value));
}

function setUpSendEmailAvailability(userField, sendEmailCheckbox) {
    function updateSendEmailAvailability() {
        if (!sendEmailCheckbox) {
            return;
        }

        if (isSelectedUserIdValue(userField?.value)) {
            sendEmailCheckbox.disabled = false;
        } else {
            // Typed emails always send an invitation email, so keep the
            // checkbox checked and disable it.
            sendEmailCheckbox.checked = true;
            sendEmailCheckbox.disabled = true;
        }
    }

    if (userField && typeof django !== "undefined" && django.jQuery) {
        django.jQuery(userField).on("change select2:select select2:clear", function() {
            updateSendEmailAvailability();
        });
    }

    updateSendEmailAvailability();
}

export function setUpUserInvitationFields(userField, sendEmailCheckbox) {
    setUpUserOrEmailAutocomplete(userField);
    setUpSendEmailAvailability(userField, sendEmailCheckbox);
}
