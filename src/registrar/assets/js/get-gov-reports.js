/** An IIFE for admin in DjangoAdmin to listen to clicks on the growth report export button,
 * attach the seleted start and end dates to a url that'll trigger the view, and finally
 * redirect to that url.
 * 
 * This function also sets the start and end dates to match the url params if they exist
*/
(function () {
    // Function to get URL parameter value by name
    function getParameterByName(name, url) {
        if (!url) url = window.location.href;
        name = name.replace(/[\[\]]/g, '\\$&');
        var regex = new RegExp('[?&]' + name + '(=([^&#]*)|&|#|$)'),
            results = regex.exec(url);
        if (!results) return null;
        if (!results[2]) return '';
        return decodeURIComponent(results[2].replace(/\+/g, ' '));
    }

    // Get the current date in the format YYYY-MM-DD
    let currentDate = new Date().toISOString().split('T')[0];

    // Default the value of the start date input field to the current date
    let startDateInput = document.getElementById('start');

    // Default the value of the end date input field to the current date
    let endDateInput = document.getElementById('end');

    let exportButtons = document.querySelectorAll('.exportLink');

    if (exportButtons.length > 0) {
        // Check if start and end dates are present in the URL
        let urlStartDate = getParameterByName('start_date');
        let urlEndDate = getParameterByName('end_date');

        // Set input values based on URL parameters or current date
        startDateInput.value = urlStartDate || currentDate;
        endDateInput.value = urlEndDate || currentDate;

        exportButtons.forEach((btn) => {
            btn.addEventListener('click', function () {
                // Get the selected start and end dates
                let startDate = startDateInput.value;
                let endDate = endDateInput.value;
                let exportUrl = btn.dataset.exportUrl;

                // Build the URL with parameters
                exportUrl += "?start_date=" + startDate + "&end_date=" + endDate;

                // Redirect to the export URL
                window.location.href = exportUrl;
            });
        });
    }

})();

/** An IIFE to initialize the analytics page
*/
(function () {
    function createComparativeColumnChart(canvasId, title, labelOne, labelTwo) {
        var canvas = document.getElementById(canvasId);
        if (!canvas) {
            return
        }

        var ctx = canvas.getContext("2d");

        var listOne = JSON.parse(canvas.getAttribute('data-list-one'));
        var listTwo = JSON.parse(canvas.getAttribute('data-list-two'));

        var data = {
            labels: ["Total", "Federal", "Interstate", "State/Territory", "Tribal", "County", "City", "Special District", "School District", "Election Board"],
            datasets: [
                {
                    label: labelOne,
                    backgroundColor: "rgba(255, 99, 132, 0.2)",
                    borderColor: "rgba(255, 99, 132, 1)",
                    borderWidth: 1,
                    data: listOne,
                },
                {
                    label: labelTwo,
                    backgroundColor: "rgba(75, 192, 192, 0.2)",
                    borderColor: "rgba(75, 192, 192, 1)",
                    borderWidth: 1,
                    data: listTwo,
                },
            ],
        };

        var options = {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                },
                title: {
                    display: true,
                    text: title
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                },
            },
        };

        new Chart(ctx, {
            type: "bar",
            data: data,
            options: options,
        });
    }

    function initComparativeColumnCharts() {
        document.addEventListener("DOMContentLoaded", function () {
            createComparativeColumnChart("myChart1", "Managed domains", "Start Date", "End Date");
            createComparativeColumnChart("myChart2", "Unmanaged domains", "Start Date", "End Date");
            createComparativeColumnChart("myChart3", "Deleted domains", "Start Date", "End Date");
            createComparativeColumnChart("myChart4", "Ready domains", "Start Date", "End Date");
            createComparativeColumnChart("myChart5", "Submitted requests", "Start Date", "End Date");
            createComparativeColumnChart("myChart6", "All requests", "Start Date", "End Date");
        });
    };
    initComparativeColumnCharts();
})();
