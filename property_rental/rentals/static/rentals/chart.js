let myChart;

document.addEventListener('DOMContentLoaded', function() {

    const form = document.getElementById('chartCustomTimeline');
    form.addEventListener('submit', handleCustomTimeline);

    const frequencyButtons = document.querySelectorAll('.chart-frequency');
    frequencyButtons.forEach(button => {
        button.addEventListener('click', async function() {
            await updateChart(myChart, this);
        });
    })
});

// Setting the chart
function typeChartInitialization(type, chartData) {
    const ctxChart = document.getElementById(`${type}BarChart`);
    myChart = new Chart(ctxChart, {
        type: 'bar',
        data: {
            labels: chartData.labels,
            datasets: chartData.datasets
            // [{
            //     data: chartData.datasets.map(value => parseFloat(value.toLocaleString())),
            // }]
        },
        plugins: [ChartDataLabels],
        options: {
            responsive: true,
            aspectRatio: 1|3,
            scales: {
                x: {
                    stacked: true,
                    grid: {
                        display: false
                    }
                },
                y: {
                    grace: '5%',
                    stacked: true,
                    title: {
                        display: true,
                        text: chartData.currency,
                    },
                    grid: {
                        display: false
                    }
                },
            },
            layout: {
                padding: 20
            },
            plugins: {
                legend: {
                    display: false, // Hide the legend
                },
                datalabels: {
                    anchor: 'end',
                    align: 'top',
                    offset: 5,
                    formatter: (value, context) => {
                        // Format the value with commas as thousand separators
                        return value.toLocaleString("en-US");
                    }
                }
            },
        },
    });
}

// Handling changing the timeline of the chart. Function referenced directly in timeline-chart.html
function changeTimeline(element) {

    const toDate = new Date(document.getElementById('chartDateTo').value);
    let fromDate;

    switch (element.value) {
        case 'YTD':
            fromDate = new Date(new Date().getFullYear(), 0, 1);
            break;
        case '3m':
            fromDate = new Date(toDate.getFullYear(), toDate.getMonth() - 3, toDate.getDate());
            break;
        case '6m':
            fromDate = new Date(toDate.getFullYear(), toDate.getMonth() - 6, toDate.getDate());
            break;
        case '12m':
            fromDate = new Date(toDate.getFullYear(), toDate.getMonth() - 12, toDate.getDate());
            break;
        case '3Y':
            fromDate = new Date(toDate.getFullYear() - 3, toDate.getMonth(), toDate.getDate());
            break;
        case '5Y':
            fromDate = new Date(toDate.getFullYear() - 5, toDate.getMonth(), toDate.getDate());
            break;
        case 'All':
            fromDate = new Date('1900-01-01');
            break;
        case 'Custom':
            let myModal = new bootstrap.Modal(document.getElementById('modalChartTimeline'), {});
            myModal.show();
            return;
    }

    // Run if case is not 'Custom'
    document.getElementById('chartDateFrom').value = convertDate(fromDate);
    updateChart(myChart, element);
}

// Convert to YYYY-mmm-dd format
function convertDate(date) {
    let day = ("0" + date.getDate()).slice(-2);
    let month = ("0" + (date.getMonth() + 1)).slice(-2);
    return date.getFullYear()+"-"+(month)+"-"+(day);
}

// Fetching data for the chart. Defined in layout.js as used on the several pages
function getChartData(type, elementId, frequency, from, to) {

    return fetch(`/get_chart_data?type=${type}&id=${elementId}&frequency=${frequency}&from=${from}&to=${to}`)
        .then(response => response.json())
        .then(chartData => {
            return chartData;
        })
        .catch(error => {
            console.error('Error fetching chart data:', error);
            return null;
        });
}

// Handling click of custom timeline modal
function handleCustomTimeline(event) {
    event.preventDefault();

    // Close the Modal
    const modalReference = document.getElementById("modalChartTimeline");
    const timelineModal = bootstrap.Modal.getInstance(modalReference);
    timelineModal.hide();

    // Feed select element as second argument to recover target correctly
    updateChart(myChart, document.getElementById("id_chartTimeline"));

}

async function updateChart(chart, element) {

    const target = element.closest('.card').getAttribute('id');

    let type;
    let elementId;

    if (target === 'homePageChartCard') {
        type = 'homePage';
        elementId = null;
    } else if (target === 'tenantChartCard') {
        type = 'tenant';
        elementId = document.getElementById("deleteButton").getAttribute(`data-${type}-id`)
    }

    const frequency = document.querySelector('input[name="chartFrequency"]:checked').value;
    const from = document.getElementById("chartDateFrom").value;
    const to = document.getElementById("chartDateTo").value;
    const chartData = await getChartData(type, elementId, frequency, from, to);

    chart.data.labels = chartData.labels;
    chart.data.datasets = chartData.datasets;
    chart.update();
    chart.draw();

    // Reapply the formatter for data labels
    // chart.data.datasets[0].datalabels.formatter = (value, context) => {
    //     // Format the value with commas as thousand separators
    //     return value.toLocaleString() + ' Q';
    //     // return "test";
    // };

    // console.log("Redrawing the chart");
    // // Redraw the chart to reflect the updated formatter
    // chart.draw();

}

// Show actual chart settings
function updateFrequencySetting(frequency) {
    const chartFrequencySettings = document.querySelectorAll('.chart-frequency');               
    for (let i = 0; i < chartFrequencySettings.length; i++) {
        if (chartFrequencySettings[i].value === frequency) {
            chartFrequencySettings[i].checked = true;
            break;
        }                
    }
}