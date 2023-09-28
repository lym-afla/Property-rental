document.addEventListener('DOMContentLoaded', function() {
    // Get all the circle elements in the Payment Schedule table
    const circles = document.querySelectorAll('.red-circle, .green-circle');
    console.log(circles.length);
    
    // Initialize a counter variable
    let loadedCircleCount = 0;
    
    // Check if all circles are already loaded (no events needed for background colors)
    circles.forEach(circle => {
        loadedCircleCount++;
    });

    // Check if all circles have been loaded
    if (loadedCircleCount === circles.length) {
        // All circles are loaded, you can now display the card content
        const paymentScheduleTable = document.getElementById('paymentScheduleTable');
        const paymentScheduleLoader = document.getElementById('paymentScheduleLoader');
        
        paymentScheduleTable.style.display = 'block';
        paymentScheduleLoader.style.display = 'none';
    }
});
