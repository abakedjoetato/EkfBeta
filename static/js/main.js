// Main JavaScript file
document.addEventListener('DOMContentLoaded', function() {
    console.log('PvP Stats Bot Dashboard Loaded');
    
    // Enable tooltips
    const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
    const tooltipList = [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
});
