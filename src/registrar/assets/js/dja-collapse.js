/*
 * We will run our own version of
 * https://github.com/django/django/blob/195d885ca01b14e3ce9a1881c3b8f7074f953736/django/contrib/admin/static/admin/js/collapse.js
 * Works with our fieldset override
*/

/*global gettext*/
'use strict';
{
    window.addEventListener('load', function() {
        // Add anchor tag for Show/Hide link
        const fieldsets = document.querySelectorAll('fieldset.collapse--dotgov');
        for (const [i, elem] of fieldsets.entries()) {
            // Don't hide if fields in this fieldset have errors
            if (elem.querySelectorAll('div.errors, ul.errorlist').length === 0) {
                elem.classList.add('collapsed');
                const button = elem.querySelector('button');
                button.id = 'fieldsetcollapser' + i;
                button.className = 'collapse-toggle--dotgov usa-button usa-button--unstyled';
            }
        }
        // Add toggle to hide/show anchor tag
        const toggleFuncDotgov = function(e) {
            e.preventDefault();
            e.stopPropagation();
            const fieldset = this.closest('fieldset');
            const spanElement = this.querySelector('span');
            const useElement = this.querySelector('use');
            if (fieldset.classList.contains('collapsed')) {
                // Show
                spanElement.textContent = 'Hide details';
                useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_less');
                fieldset.classList.remove('collapsed');
            } else {
                // Hide
                spanElement.textContent = 'Show details';
                useElement.setAttribute('xlink:href', '/public/img/sprite.svg#expand_more');
                fieldset.classList.add('collapsed');
            }
        };
        document.querySelectorAll('.collapse-toggle--dotgov').forEach(function(el) {
            el.addEventListener('click', toggleFuncDotgov);
        });
    });
}