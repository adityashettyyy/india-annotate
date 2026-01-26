// IndiaAnnotate - COCO Dataset Validator Frontend Script
const API_BASE_URL = window.API_BASE_URL || 'http://127.0.0.1:5000';

let selectedFile = null;
let currentResult = null;

// Initialize theme
document.addEventListener('DOMContentLoaded', function() {
    initializeTheme();
    checkAPIStatus();
});

// Theme Management
function initializeTheme() {
    const themeToggle = document.getElementById('themeToggle');
    const sunIcon = document.getElementById('sunIcon');
    const moonIcon = document.getElementById('moonIcon');

    if (!themeToggle || !sunIcon || !moonIcon) return;

    // Check saved theme or prefer dark mode
    const savedTheme = localStorage.getItem('theme');
    const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    
    if (savedTheme === 'dark' || (!savedTheme && prefersDark)) {
        document.documentElement.classList.add('dark');
        sunIcon.classList.add('hidden');
        moonIcon.classList.remove('hidden');
    } else {
        document.documentElement.classList.remove('dark');
        sunIcon.classList.remove('hidden');
        moonIcon.classList.add('hidden');
    }
    
    // Toggle theme
    themeToggle.addEventListener('click', () => {
        if (document.documentElement.classList.contains('dark')) {
            document.documentElement.classList.remove('dark');
            localStorage.setItem('theme', 'light');
            sunIcon.classList.remove('hidden');
            moonIcon.classList.add('hidden');
        } else {
            document.documentElement.classList.add('dark');
            localStorage.setItem('theme', 'dark');
            sunIcon.classList.add('hidden');
            moonIcon.classList.remove('hidden');
        }
    });
}

// Check API status on load
async function checkAPIStatus() {
    const statusElement = document.getElementById('apiStatus');
    
    try {
        const response = await fetch(API_BASE_URL);
        if (response.ok) {
            statusElement.textContent = 'Connected';
            statusElement.className = 'font-medium text-green-600 dark:text-green-400';
        } else {
            statusElement.textContent = 'Error';
            statusElement.className = 'font-medium text-red-600 dark:text-red-400';
        }
    } catch (error) {
        statusElement.textContent = 'Disconnected';
        statusElement.className = 'font-medium text-red-600 dark:text-red-400';
    }
}

// Handle file selection
function handleFileSelect(event) {
    const file = event.target.files[0];
    if (!file) return;

    // Check file type
    if (!file.name.endsWith('.json')) {
        showError('Please select a JSON file');
        return;
    }

    // Check file size (max 10MB)
    if (file.size > 10 * 1024 * 1024) {
        showError('File size must be less than 10MB');
        return;
    }

    selectedFile = file;
    displaySelectedFile();
}

// Display selected file information
function displaySelectedFile() {
    const container = document.getElementById('selectedFile');
    const fileName = document.getElementById('fileName');
    const fileSize = document.getElementById('fileSize');
    const validateBtn = document.getElementById('validateBtn');

    // Format file size
    const sizeInMB = (selectedFile.size / (1024 * 1024)).toFixed(2);

    fileName.textContent = selectedFile.name;
    fileSize.textContent = `${sizeInMB} MB`;

    container.classList.remove('hidden');
    validateBtn.disabled = false;
}

// Clear selected file
function clearFile() {
    selectedFile = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('selectedFile').classList.add('hidden');
    document.getElementById('validateBtn').disabled = true;
}

// Validate dataset with the API
async function validateDataset() {
    if (!selectedFile) {
        showError('Please select a file first');
        return;
    }

    // Get elements
    const validateBtn = document.getElementById('validateBtn');
    const spinner = document.getElementById('loadingSpinner');
    const validateText = document.getElementById('validateText');

    // Show loading
    validateBtn.disabled = true;
    spinner.classList.remove('hidden');
    validateText.textContent = "Validating...";

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
        const response = await fetch(`${API_BASE_URL}/validate`, {
            method: 'POST',
            body: formData
        });

        const result = await response.json();
        if (!response.ok || result.status !== 'success') {
            showError(result.message || 'Validation failed');
            return;
        }

        currentResult = result;
        displayResults(result);

    } catch (error) {
        showError(`Network error: ${error.message}`);
    }

    // Always reset UI
    validateBtn.disabled = false;
    spinner.classList.add('hidden');
    validateText.textContent = "Validate Dataset";
}

/* ============================================================
   AUTO-ANNOTATE RAW IMAGES (NEW)
   Calls backend /auto-annotate and directly shows validation.
============================================================ */
async function runAutoAnnotate() {
    const splitSelect = document.getElementById('splitSelect');
    const autoSpinner = document.getElementById('autoAnnSpinner');

    // Select the correct button from HTML
    const autoBtn = document.getElementById('autoAnnotateBtn');

    if (!splitSelect) {
        showError("Auto-annotate UI not found.");
        return;
    }

    const split = splitSelect.value;

    // UI loading state
    if (autoBtn) autoBtn.disabled = true;
    if (autoSpinner) autoSpinner.classList.remove("hidden");

    try {
        const response = await fetch(`${API_BASE_URL}/auto-annotate`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ split })
        });

        const data = await response.json();

        if (!response.ok || data.status !== "success") {
            showError(data.message || "Auto-annotation failed");
            return;
        }

        // If backend also returned validation results
        if (data.validation_report) {
            currentResult = data.validation_report;
            displayResults(currentResult);
        }


        showSuccess(data.message || "Auto-annotation completed!");

    } catch (err) {
        showError("Auto-annotate error: " + err.message);
    } finally {
        if (autoBtn) autoBtn.disabled = false;
        if (autoSpinner) autoSpinner.classList.add("hidden");
    }
}


// Display validation results
function displayResults(result) {
    // Hide empty state and show results section
    const emptyState = document.getElementById('emptyState');
    const resultsSection = document.getElementById('resultsSection');
    
    emptyState.classList.add('hidden');
    resultsSection.classList.remove('hidden');

    // Update status card
    updateStatusCard(result);

    // Update summary cards
    updateSummaryCards(result);

    // Update label distribution
    updateLabelDistribution(result);

    // Update JSON viewer
    updateJSONViewer(result);
}

// Update status card based on result
function updateStatusCard(result) {
    const statusIcon = document.getElementById('statusIcon');
    const statusTitle = document.getElementById('statusTitle');
    const statusMessage = document.getElementById('statusMessage');
    const qualityScore = document.getElementById('qualityScore');
    const scoreValue = document.getElementById('scoreValue');

    if (result.status === 'success') {
        // Success state
        statusIcon.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center">
                <svg class="w-6 h-6 text-green-600 dark:text-green-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                </svg>
            </div>
        `;
        statusTitle.textContent = 'Validation Successful';
        statusTitle.className = 'font-semibold text-lg text-green-700 dark:text-green-400';
        statusMessage.textContent = 'Your COCO dataset is valid and ready for use.';
        
        // Show quality score
        if (result.summary?.estimated_quality_score) {
            qualityScore.classList.remove('hidden');
            const score = result.summary.estimated_quality_score;
            scoreValue.textContent = score;
            
            if (score >= 80) {
                scoreValue.className = 'text-2xl font-bold text-green-600 dark:text-green-400';
            } else if (score >= 60) {
                scoreValue.className = 'text-2xl font-bold text-yellow-600 dark:text-yellow-400';
            } else {
                scoreValue.className = 'text-2xl font-bold text-red-600 dark:text-red-400';
            }
        }
    } else {
        // Error state
        statusIcon.innerHTML = `
            <div class="w-10 h-10 rounded-full bg-red-100 dark:bg-red-900/30 flex items-center justify-center">
                <svg class="w-6 h-6 text-red-600 dark:text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </div>
        `;
        statusTitle.textContent = 'Validation Failed';
        statusTitle.className = 'font-semibold text-lg text-red-700 dark:text-red-400';
        statusMessage.textContent = result.message || 'There was an error validating your dataset.';
        qualityScore.classList.add('hidden');
    }
}

// Update summary statistics cards
function updateSummaryCards(result) {
    const container = document.getElementById('summaryCards');
    
    if (!result.summary) {
        container.innerHTML = '<p class="text-gray-600 dark:text-gray-400">No summary data available.</p>';
        return;
    }

    const summaryData = [
        {
            title: 'Images',
            value: result.summary.num_images || 0,
            icon: '🖼️',
            color: 'blue',
            percentage: 100
        },
        {
            title: 'Annotations',
            value: result.summary.num_annotations || 0,
            icon: '📝',
            color: 'green',
            percentage: result.summary.num_images ? 
                Math.min((result.summary.num_annotations / (result.summary.num_images * 10)) * 100, 100) : 0
        },
        {
            title: 'Categories',
            value: result.summary.num_categories || 0,
            icon: '🏷️',
            color: 'purple',
            percentage: Math.min((result.summary.num_categories / 20) * 100, 100)
        },
        {
            title: 'Annotated Images',
            value: result.summary.images_with_annotations || 0,
            icon: '✅',
            color: 'teal',
            percentage: result.summary.num_images ? 
                (result.summary.images_with_annotations / result.summary.num_images) * 100 : 0
        },
        {
            title: 'Unannotated Images',
            value: result.summary.images_without_annotations || 0,
            icon: '⭕',
            color: 'orange',
            percentage: result.summary.num_images ? 
                (result.summary.images_without_annotations / result.summary.num_images) * 100 : 0
        },
        {
            title: 'Avg. per Image',
            value: result.summary.num_images ? 
                (result.summary.num_annotations / result.summary.num_images).toFixed(1) : '0',
            icon: '📊',
            color: 'indigo',
            percentage: Math.min((result.summary.num_annotations / (result.summary.num_images * 5)) * 100, 100)
        }
    ];

    container.innerHTML = summaryData.map(item => `
        <div class="bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-xl p-5 hover-lift">
            <div class="flex items-center justify-between">
                <div>
                    <p class="text-sm text-gray-500 dark:text-gray-400 font-medium mb-1">${item.title}</p>
                    <p class="text-2xl font-bold text-gray-900 dark:text-white">${item.value}</p>
                </div>
                <div class="text-2xl">${item.icon}</div>
            </div>
            <div class="mt-4 h-1 w-full bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                <div class="h-full bg-${item.color}-500 rounded-full" style="width: ${item.percentage}%"></div>
            </div>
        </div>
    `).join('');
}

// Update label distribution section
function updateLabelDistribution(result) {
    const container = document.getElementById('distributionSection');
    const grid = document.getElementById('distributionGrid');
    const totalAnnotationsEl = document.getElementById('totalAnnotations');
    
    if (!result.label_distribution || Object.keys(result.label_distribution).length === 0) {
        container.classList.add('hidden');
        return;
    }

    container.classList.remove('hidden');
    
    const totalAnnotations = result.summary?.num_annotations || 1;
    const distribution = result.label_distribution;
    
    totalAnnotationsEl.textContent = `Total: ${totalAnnotations} annotations`;
    
    grid.innerHTML = Object.entries(distribution).map(([label, data]) => {
        const percentage = ((data.count / totalAnnotations) * 100).toFixed(1);
        const width = Math.min(percentage, 100);
        
        return `
            <div class="border border-gray-200 dark:border-gray-700 rounded-lg p-4 hover:bg-gray-50 dark:hover:bg-gray-700/50 transition-colors">
                <div class="flex items-center justify-between mb-2">
                    <span class="font-medium text-gray-900 dark:text-white truncate">${label}</span>
                    <span class="text-sm font-medium text-primary-600 dark:text-primary-400 flex-shrink-0 ml-2">${data.count}</span>
                </div>
                <div class="flex items-center space-x-2">
                    <div class="flex-1 h-2 bg-gray-100 dark:bg-gray-700 rounded-full overflow-hidden">
                        <div class="h-full bg-primary-500 rounded-full" style="width: ${width}%"></div>
                    </div>
                    <span class="text-xs text-gray-500 dark:text-gray-400 font-medium">${percentage}%</span>
                </div>
                <div class="mt-2 text-xs text-gray-500 dark:text-gray-400">
                    Category ID: ${data.category_id}
                </div>
            </div>
        `;
    }).join('');
}

// Update JSON viewer with syntax highlighting
function updateJSONViewer(result) {
    const jsonOutput = document.getElementById('jsonOutput');
    const jsonString = JSON.stringify(result, null, 2);
    
    // Basic syntax highlighting
    const highlighted = jsonString
        .replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\s*:)?)/g, function(match) {
            let cls = 'json-key';
            if (/:$/.test(match)) {
                return `<span class="${cls}">${match}</span>`;
            }
            return `<span class="json-string">${match}</span>`;
        })
        .replace(/\b(true|false)\b/g, '<span class="json-boolean">$1</span>')
        .replace(/\b(null)\b/g, '<span class="json-null">$1</span>')
        .replace(/\b(\d+)\b/g, '<span class="json-number">$1</span>');

    jsonOutput.innerHTML = highlighted;
}

// Toggle raw JSON view
function toggleRawJSON() {
    const jsonViewer = document.getElementById('jsonViewer');
    const toggleBtn = document.querySelector('button[onclick="toggleRawJSON()"]');
    
    if (jsonViewer.classList.contains('max-h-96')) {
        jsonViewer.classList.remove('max-h-96');
        jsonViewer.classList.add('max-h-screen');
        toggleBtn.textContent = 'Collapse View';
    } else {
        jsonViewer.classList.remove('max-h-screen');
        jsonViewer.classList.add('max-h-96');
        toggleBtn.textContent = 'Expand View';
    }
}

// Copy JSON to clipboard
function copyJSON() {
    if (!currentResult) return;
    
    const jsonString = JSON.stringify(currentResult, null, 2);
    
    navigator.clipboard.writeText(jsonString).then(() => {
        showSuccess('JSON copied to clipboard!');
    }).catch(err => {
        showError('Failed to copy JSON: ' + err.message);
    });
}

// Download validation report
function downloadReport() {
    if (!currentResult) {
        showError('No validation results to download');
        return;
    }

    const blob = new Blob([JSON.stringify(currentResult, null, 2)], {
        type: "application/json"
    });
    const url = URL.createObjectURL(blob);

    const a = document.createElement("a");
    a.href = url;
    a.download = `validation_report_${new Date().toISOString().slice(0, 10)}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    
    showSuccess('Report downloaded successfully!');
}

// Reset page to initial state
function resetPage() {
    // Clear file input
    selectedFile = null;
    currentResult = null;
    document.getElementById('fileInput').value = '';
    document.getElementById('selectedFile').classList.add('hidden');

    // Reset validation button text + spinner
    const validateBtn = document.getElementById('validateBtn');
    const validateText = document.getElementById('validateText');
    const spinner = document.getElementById('loadingSpinner');

    validateBtn.disabled = true;
    validateText.textContent = "Validate Dataset";
    spinner.classList.add("hidden");  // keep spinner hidden

    // Hide results section and show empty state
    document.getElementById('resultsSection').classList.add('hidden');
    document.getElementById('emptyState').classList.remove('hidden');

    // Reset JSON viewer size
    const jsonViewer = document.getElementById('jsonViewer');
    const toggleBtn = document.querySelector('button[onclick="toggleRawJSON()"]');

    jsonViewer.classList.remove('max-h-screen');
    jsonViewer.classList.add('max-h-96');

    if (toggleBtn) toggleBtn.textContent = 'Toggle Full View';

    // Success message
    showSuccess('Page has been reset');
}

// Load sample data for demonstration
function loadSample() {
    // Create a sample COCO format JSON
    const sampleData = {
        status: "success",
        summary: {
            num_images: 145,
            num_annotations: 892,
            num_categories: 8,
            images_with_annotations: 142,
            images_without_annotations: 3,
            estimated_quality_score: 85
        },
        label_distribution: {
            "person": { category_id: "1", count: 234 },
            "car": { category_id: "2", count: 312 },
            "motorcycle": { category_id: "3", count: 89 },
            "autorickshaw": { category_id: "4", count: 156 },
            "bus": { category_id: "5", count: 45 },
            "truck": { category_id: "6", count: 32 },
            "traffic light": { category_id: "7", count: 12 },
            "traffic sign": { category_id: "8", count: 12 }
        },
        notes: [
            "Validated using external schema.json",
            "COCO-style dataset structure",
            "Quality score is heuristic-based (customizable)"
        ]
    };

    // Display the sample results
    currentResult = sampleData;
    displayResults(sampleData);
    
    // Show notification
    showSuccess('Sample data loaded successfully!');
}

// Show error message
function showError(message) {
    showNotification(message, 'error');
}

// Show success message
function showSuccess(message) {
    showNotification(message, 'success');
}

// Show notification
function showNotification(message, type = 'info') {
    // Remove existing notifications
    const existingNotifications = document.querySelectorAll('.notification');
    existingNotifications.forEach(notification => {
        notification.classList.add('hiding');
        setTimeout(() => notification.remove(), 300);
    });

    // Create notification element
    const notification = document.createElement('div');
    notification.className = `fixed top-4 right-4 px-4 py-3 rounded-lg shadow-lg z-50 notification ${
        type === 'error' ? 'bg-red-50 dark:bg-red-900/30 border border-red-200 dark:border-red-800 text-red-700 dark:text-red-400' :
        type === 'success' ? 'bg-green-50 dark:bg-green-900/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-400' :
        'bg-blue-50 dark:bg-blue-900/30 border border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400'
    }`;
    
    const icon = type === 'error' ? '❌' : type === 'success' ? '✅' : 'ℹ️';
    
    notification.innerHTML = `
        <div class="flex items-center space-x-2">
            <span>${icon}</span>
            <span>${message}</span>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Remove notification after 5 seconds
    setTimeout(() => {
        notification.classList.add('hiding');
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 300);
    }, 5000);
}
