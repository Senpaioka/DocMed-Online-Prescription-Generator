/**
 * DocMed Real-Time SSE Notification System
 * Handles Server-Sent Events, Live Notification Bell, Floating Toasts & Audio Chimes.
 */

(function() {
    'use strict';

    if (window._docMedSSEInitialized) {
        return;
    }
    window._docMedSSEInitialized = true;

    // Check if user is authenticated (data attribute on body or window)
    const userMeta = document.querySelector('meta[name="user-id"]');
    if (!userMeta || !userMeta.content) {
        return; // User is not authenticated, do not start SSE
    }

    const userId = parseInt(userMeta.content, 10);
    let eventSource = null;
    let notifications = [];
    let unreadCount = 0;
    let audioContext = null;

    // Soft, pleasant notification chime using Web Audio API
    function playNotificationSound() {
        try {
            if (!audioContext) {
                audioContext = new (window.AudioContext || window.webkitAudioContext)();
            }
            if (audioContext.state === 'suspended') {
                audioContext.resume();
            }
            const now = audioContext.currentTime;

            // Note 1 (E5 - 659Hz)
            const osc1 = audioContext.createOscillator();
            const gain1 = audioContext.createGain();
            osc1.type = 'sine';
            osc1.frequency.setValueAtTime(659.25, now);
            gain1.gain.setValueAtTime(0.08, now);
            gain1.gain.exponentialRampToValueAtTime(0.001, now + 0.15);
            osc1.connect(gain1);
            gain1.connect(audioContext.destination);
            osc1.start(now);
            osc1.stop(now + 0.15);

            // Note 2 (A5 - 880Hz)
            const osc2 = audioContext.createOscillator();
            const gain2 = audioContext.createGain();
            osc2.type = 'sine';
            osc2.frequency.setValueAtTime(880, now + 0.08);
            gain2.gain.setValueAtTime(0.1, now + 0.08);
            gain2.gain.exponentialRampToValueAtTime(0.001, now + 0.35);
            osc2.connect(gain2);
            gain2.connect(audioContext.destination);
            osc2.start(now + 0.08);
            osc2.stop(now + 0.35);
        } catch (e) {
            console.debug('[DocMed SSE] Audio chime not allowed or supported:', e);
        }
    }

    // UI Helpers
    function updateBellBadge(count) {
        unreadCount = count;
        const badge = document.getElementById('notif-badge');
        const bellIcon = document.getElementById('notif-bell-icon');
        if (!badge) return;

        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.style.display = 'inline-flex';
            if (bellIcon) {
                bellIcon.classList.add('notif-bell-ring');
                setTimeout(() => bellIcon.classList.remove('notif-bell-ring'), 1000);
            }
        } else {
            badge.style.display = 'none';
        }
    }

    function renderNotificationItem(item) {
        let iconClass = 'fa-calendar-check text-success';
        let bgLight = '#f0fdf4';
        
        if (item.event_type === 'appointment_rejected' || item.event_type === 'appointment_cancelled') {
            iconClass = 'fa-calendar-xmark text-danger';
            bgLight = '#fef2f2';
        } else if (item.event_type === 'appointment_completed') {
            iconClass = 'fa-file-prescription text-teal';
            bgLight = '#f0fdfa';
        } else if (item.event_type === 'new_appointment_request') {
            iconClass = 'fa-user-clock text-warning';
            bgLight = '#fffbeb';
        }

        const unreadIndicator = !item.is_read ? `<span class="notif-dot"></span>` : '';
        const link = item.link_url || '#';

        return `
            <a href="${link}" class="notif-item ${!item.is_read ? 'unread' : ''}" data-id="${item.id}" onclick="DocMedNotifications.markRead(${item.id})">
                <div class="notif-icon-box" style="background:${bgLight};">
                    <i class="fa-solid ${iconClass}"></i>
                </div>
                <div class="notif-content">
                    <div class="d-flex justify-content-between align-items-baseline">
                        <h6 class="notif-title">${escapeHtml(item.title)}</h6>
                        <small class="notif-time">${item.time_ago || 'Just now'}</small>
                    </div>
                    <p class="notif-desc mb-0">${escapeHtml(item.message)}</p>
                </div>
                ${unreadIndicator}
            </a>
        `;
    }

    function escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    function renderNotificationList() {
        const container = document.getElementById('notif-list-container');
        if (!container) return;

        if (notifications.length === 0) {
            container.innerHTML = `
                <div class="text-center py-4 text-muted">
                    <i class="fa-regular fa-bell-slash fs-3 mb-2 opacity-50"></i>
                    <p class="small mb-0">No notifications yet</p>
                </div>
            `;
            return;
        }

        container.innerHTML = notifications.map(renderNotificationItem).join('');
    }

    // Display Modern Floating Toast
    function showNotificationToast(item) {
        const container = document.getElementById('docmed-toast-container');
        if (!container) return;

        let icon = 'fa-calendar-check text-success';
        let borderColor = '#0d9488';
        if (item.event_type === 'appointment_rejected' || item.event_type === 'appointment_cancelled') {
            icon = 'fa-triangle-exclamation text-danger';
            borderColor = '#ef4444';
        } else if (item.event_type === 'appointment_completed') {
            icon = 'fa-file-prescription text-teal';
            borderColor = '#14b8a6';
        } else if (item.event_type === 'new_appointment_request') {
            icon = 'fa-user-clock text-warning';
            borderColor = '#f59e0b';
        }

        const toast = document.createElement('div');
        toast.className = 'docmed-toast shadow-lg';
        toast.style.borderLeftColor = borderColor;
        toast.innerHTML = `
            <div class="d-flex align-items-start gap-3">
                <div class="toast-icon">
                    <i class="fa-solid ${icon} fs-5"></i>
                </div>
                <div class="toast-body-content flex-grow-1">
                    <div class="d-flex justify-content-between align-items-center mb-1">
                        <strong class="toast-title">${escapeHtml(item.title)}</strong>
                        <small class="text-muted">Just now</small>
                    </div>
                    <p class="toast-msg mb-2">${escapeHtml(item.message)}</p>
                    ${item.link_url ? `<a href="${item.link_url}" class="toast-action-btn">View Details &rarr;</a>` : ''}
                </div>
                <button type="button" class="btn-close btn-close-sm toast-dismiss" aria-label="Close"></button>
            </div>
        `;

        const dismissBtn = toast.querySelector('.toast-dismiss');
        dismissBtn.addEventListener('click', () => {
            toast.classList.add('hide');
            setTimeout(() => toast.remove(), 300);
        });

        container.appendChild(toast);

        // Slide in
        requestAnimationFrame(() => {
            toast.classList.add('show');
        });

        // Auto remove after 7 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.classList.remove('show');
                toast.classList.add('hide');
                setTimeout(() => toast.remove(), 300);
            }
        }, 7000);
    }

    // Fetch initial notifications via API
    function fetchNotifications() {
        fetch('/dashboard/notifications/api')
            .then(res => res.json())
            .then(data => {
                if (data.status === 'success') {
                    notifications = data.notifications || [];
                    updateBellBadge(data.unread_count || 0);
                    renderNotificationList();
                }
            })
            .catch(err => console.debug('[DocMed SSE] Error fetching notifications:', err));
    }

    // Connect to SSE stream
    function initSSE() {
        if (eventSource) {
            eventSource.close();
        }

        console.log('[DocMed SSE] Connecting to notification stream...');
        eventSource = new EventSource('/dashboard/notifications/stream');

        eventSource.onopen = function() {
            console.log('[DocMed SSE] Connection established.');
        };

        // Handle connected greeting
        eventSource.addEventListener('connected', function(e) {
            try {
                const data = JSON.parse(e.data);
                if (typeof data.unread_count === 'number') {
                    updateBellBadge(data.unread_count);
                }
            } catch (err) {
                console.debug('[DocMed SSE] Parse error on connected:', err);
            }
        });

        // Common handler for appointment events
        const appointmentEvents = [
            'appointment_confirmed',
            'appointment_rejected',
            'appointment_cancelled',
            'appointment_completed',
            'new_appointment_request'
        ];

        const processedEventIds = new Set();

        appointmentEvents.forEach(eventType => {
            eventSource.addEventListener(eventType, function(e) {
                try {
                    const item = JSON.parse(e.data);
                    console.log(`[DocMed SSE] Received ${eventType}:`, item);

                    // De-duplicate if the same notification ID or event was already processed
                    const eventKey = item.id ? `id_${item.id}` : `${eventType}_${item.created_at || ''}_${item.message || ''}`;
                    if (processedEventIds.has(eventKey)) {
                        console.debug(`[DocMed SSE] Ignoring duplicate event: ${eventKey}`);
                        return;
                    }
                    processedEventIds.add(eventKey);
                    // Keep set compact
                    if (processedEventIds.size > 200) {
                        const firstEntry = processedEventIds.values().next().value;
                        processedEventIds.delete(firstEntry);
                    }

                    // Check if already in notifications list by ID
                    if (item.id && notifications.some(n => n.id === item.id)) {
                        return;
                    }

                    // Prepend to notification list
                    notifications.unshift(item);
                    if (notifications.length > 30) notifications.pop();
                    
                    const newUnread = (typeof item.unread_count === 'number') ? item.unread_count : unreadCount + 1;
                    updateBellBadge(newUnread);
                    renderNotificationList();

                    // Play audio and show toast
                    playNotificationSound();
                    showNotificationToast(item);

                    // Broadcast custom event for page listeners (e.g. appointments list feed)
                    window.dispatchEvent(new CustomEvent('docmed:appointment_update', {
                        detail: { eventType: eventType, data: item }
                    }));
                } catch (err) {
                    console.error('[DocMed SSE] Failed to process event:', err);
                }
            });
        });

        eventSource.onerror = function(err) {
            console.debug('[DocMed SSE] Connection error, will retry automatically...', err);
        };
    }

    // Expose global methods
    window.DocMedNotifications = {
        markRead: function(id) {
            fetch(`/dashboard/notifications/mark-read/${id}`, {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(res => res.json())
            .then(data => {
                const item = notifications.find(n => n.id === id);
                if (item) item.is_read = true;
                updateBellBadge(data.unread_count || 0);
                renderNotificationList();
            })
            .catch(err => console.error('[DocMed SSE] Error marking read:', err));
        },
        markAllRead: function() {
            fetch('/dashboard/notifications/mark-all-read', {
                method: 'POST',
                headers: { 'X-Requested-With': 'XMLHttpRequest' }
            })
            .then(res => res.json())
            .then(data => {
                notifications.forEach(n => n.is_read = true);
                updateBellBadge(0);
                renderNotificationList();
            })
            .catch(err => console.error('[DocMed SSE] Error marking all read:', err));
        }
    };

    // Initialize on DOM load
    document.addEventListener('DOMContentLoaded', function() {
        fetchNotifications();
        initSSE();
    });

    // Clean up on page unload
    window.addEventListener('beforeunload', function() {
        if (eventSource) {
            eventSource.close();
        }
    });

})();
