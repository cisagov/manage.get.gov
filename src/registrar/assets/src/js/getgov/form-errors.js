export function initFormErrorHandling() {
  document.addEventListener('DOMContentLoaded', function() {
    const errorSummary = document.getElementById('form-errors');
    const firstErrorField = document.querySelector('.usa-input--error');
    if (firstErrorField) {
      // Scroll to the first field in error
      firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
  
      // Add focus to the first field in error
      setTimeout(() => {
        firstErrorField.focus();
      }, 50);
    } else if (errorSummary) {
      // Scroll to the error summary
      errorSummary.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

  });
}