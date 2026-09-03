// Booking functionality
class BookingManager {
    constructor() {
        this.init();
    }
    
    init() {
        this.bindEvents();
        this.setMinimumDates();
    }
    
    bindEvents() {
        // Booking form submission
        document.addEventListener('submit', (e) => {
            if (e.target.id === 'bookingForm') {
                e.preventDefault();
                this.handleBookingSubmission(e.target);
            }
        });
        
        // Availability checking
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="check-availability"]')) {
                e.preventDefault();
                this.checkAvailability(e.target);
            }
        });
        
        // Wishlist actions
        document.addEventListener('click', (e) => {
            if (e.target.matches('[data-action="add-wishlist"]')) {
                e.preventDefault();
                this.addToWishlist(e.target);
            }
        });
    }
    
    setMinimumDates() {
        const today = new Date().toISOString().split('T')[0];
        const dateInputs = document.querySelectorAll('input[type="date"]');
        
        dateInputs.forEach(input => {
            if (!input.min) {
                input.min = today;
            }
        });
    }
    
    async checkAvailability(element) {
        const serviceType = element.dataset.serviceType;
        const serviceId = element.dataset.serviceId;
        const form = element.closest('form');
        
        if (!form) return;
        
        const formData = new FormData(form);
        const params = new URLSearchParams();
        
        params.append('service_type', serviceType);
        params.append('service_id', serviceId);
        
        for (let [key, value] of formData.entries()) {
            params.append(key, value);
        }
        
        try {
            this.showLoading(element);
            
            const response = await fetch(`/bookings/check-availability/?${params}`);
            const data = await response.json();
            
            this.hideLoading(element);
            this.displayAvailabilityResult(data, element);
            
        } catch (error) {
            this.hideLoading(element);
            this.showNotification('Error checking availability. Please try again.', 'error');
        }
    }
    
    displayAvailabilityResult(data, element) {
        const resultContainer = element.closest('.card').querySelector('.availability-result') || 
                               this.createResultContainer(element);
        
        if (data.success && data.available) {
            resultContainer.innerHTML = `
                <div class="alert alert-success">
                    <i class="bi bi-check-circle me-2"></i>
                    Available! Total: $${data.total_price}
                    ${data.nights ? ` for ${data.nights} night${data.nights > 1 ? 's' : ''}` : ''}
                    <button class="btn btn-success btn-sm ms-2" onclick="bookingManager.openBookingModal('${element.dataset.serviceType}', ${element.dataset.serviceId})">
                        Book Now
                    </button>
                </div>
            `;
        } else {
            resultContainer.innerHTML = `
                <div class="alert alert-warning">
                    <i class="bi bi-exclamation-triangle me-2"></i>
                    ${data.message || 'Not available for selected dates.'}
                </div>
            `;
        }
    }
    
    createResultContainer(element) {
        const container = document.createElement('div');
        container.className = 'availability-result mt-3';
        element.closest('.card-body').appendChild(container);
        return container;
    }
    
    async addToWishlist(element) {
        const serviceType = element.dataset.serviceType;
        const serviceId = element.dataset.serviceId;
        
        const formData = new FormData();
        formData.append('service_type', serviceType);
        formData.append('service_id', serviceId);
        formData.append('csrfmiddlewaretoken', this.getCSRFToken());
        
        try {
            const response = await fetch('/bookings/add-to-wishlist/', {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update button state
                element.innerHTML = '<i class="bi bi-heart-fill"></i> In Wishlist';
                element.classList.remove('btn-outline-primary');
                element.classList.add('btn-success');
                element.disabled = true;
                
                this.showNotification(data.message, 'success');
            } else {
                this.showNotification(data.message, 'error');
            }
            
        } catch (error) {
            this.showNotification('Error adding to wishlist. Please try again.', 'error');
        }
    }
    
    openBookingModal(serviceType, serviceId) {
        const modal = document.getElementById('bookingModal');
        if (modal) {
            const bsModal = new bootstrap.Modal(modal);
            
            // Set service details
            document.getElementById('modalServiceType').value = serviceType;
            document.getElementById('modalServiceId').value = serviceId;
            
            bsModal.show();
        }
    }
    
    async handleBookingSubmission(form) {
        const formData = new FormData(form);
        
        try {
            this.showLoading();
            
            const response = await fetch(form.action, {
                method: 'POST',
                body: formData,
                headers: {
                    'X-Requested-With': 'XMLHttpRequest'
                }
            });

            const contentType = response.headers.get('content-type') || '';
            const data = contentType.includes('application/json')
                ? await response.json()
                : null;

            if (response.ok) {
                this.showNotification('Booking created successfully!', 'success');
                setTimeout(() => {
                    window.location.href = response.redirected
                        ? response.url
                        : '/users/bookings/';
                }, 1500);
            } else {
                this.showNotification(
                    data?.message || 'Error creating booking. Please try again.',
                    'error'
                );
            }
            
        } catch (error) {
            this.showNotification('Error creating booking. Please try again.', 'error');
        } finally {
            this.hideLoading();
        }
    }
    
    showLoading(element = null) {
        if (element) {
            element.disabled = true;
            element.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Loading...';
        } else {
            document.getElementById('loadingOverlay')?.classList.add('show');
        }
    }
    
    hideLoading(element = null) {
        if (element) {
            element.disabled = false;
            // Restore original text - this would need to be stored
        } else {
            document.getElementById('loadingOverlay')?.classList.remove('show');
        }
    }
    
    showNotification(message, type) {
        const alertClass = type === 'success' ? 'alert-success' : type === 'warning' ? 'alert-warning' : 'alert-danger';
        const icon = type === 'success' ? 'check-circle' : type === 'warning' ? 'exclamation-triangle' : 'x-circle';
        
        const notification = document.createElement('div');
        notification.className = `alert ${alertClass} alert-dismissible fade show position-fixed`;
        notification.style.cssText = 'top: 80px; right: 20px; z-index: 9999; min-width: 300px;';
        notification.innerHTML = `
            <i class="bi bi-${icon} me-2"></i>${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }
    
    getCSRFToken() {
        return document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
    }
}

// Initialize booking manager when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.bookingManager = new BookingManager();
});
