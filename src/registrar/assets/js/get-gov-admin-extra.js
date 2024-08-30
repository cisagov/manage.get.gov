// Use Django's jQuery with Select2 to make the user select on the user transfer view a combobox
(function($) {
    $(document).ready(function() {
        if ($) {
            $("#selected_user").select2({
                width: 'resolve',
                placeholder: 'Select a user',
                allowClear: true
            });
        } else {
            console.error('jQuery is not available');
        }
    });
})(window.jQuery);
