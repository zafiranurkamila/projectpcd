const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const progressContainer = document.getElementById('uploadProgress');
let currentUser = JSON.parse(localStorage.getItem('user'));

const progressFill = document.getElementById('progressFill');
const progressText = document.getElementById('progressText');
const downloadZone = document.getElementById('downloadZone');
const archivesTable = document.getElementById('archivesTable').querySelector('tbody');

let lastUploadedId = null;

// URL Backend API
const API_BASE_URL = 'http://127.0.0.1:8000';

const formatBytes = (bytes) => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
};

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});

dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});

dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
        handleUpload(e.dataTransfer.files[0]);
    }
});

fileInput.addEventListener('change', (e) => {
    if (e.target.files.length) {
        handleUpload(e.target.files[0]);
    }
});

async function loadDashboard() {
    if (!currentUser) return;
    try {
        const res = await fetch(`${API_BASE_URL}/api/archives?user_id=${currentUser.id}`);
        const data = await res.json();
        
        let totalOriginal = 0;
        let totalCompressed = 0;
        let totalRatio = 0;

        archivesTable.innerHTML = '';

        data.forEach(item => {
            totalOriginal += item.original_size;
            totalCompressed += item.compressed_size;
            totalRatio += item.compression_ratio;

            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><i class="ri-file-image-line" style="margin-right:8px; color:#4a90e2;"></i> ${item.original_filename}</td>
                <td>${formatBytes(item.original_size)}</td>
                <td>${formatBytes(item.compressed_size)}</td>
                <td><span class="badge">${item.compression_ratio.toFixed(2)}x</span></td>
                <td>${item.processing_time_ms.toFixed(2)} ms</td>
                <td>
                    <div style="display: flex; gap: 8px;">
                        <button class="btn-download" onclick="window.open('${API_BASE_URL}/download/${item.id}')" title="Unduh Gambar Asli">
                            <i class="ri-download-cloud-2-line"></i> Unduh
                        </button>
                        <button class="btn-delete" onclick="deleteArchive(${item.id})" title="Hapus Data">
                            <i class="ri-delete-bin-line"></i>
                        </button>
                    </div>
                </td>
            `;
            archivesTable.appendChild(tr);
        });

        document.getElementById('totalFiles').innerText = data.length;
        
        if (data.length > 0) {
            const saved = totalOriginal - totalCompressed;
            document.getElementById('spaceSaved').innerText = formatBytes(saved);
            document.getElementById('avgRatio').innerText = (totalRatio / data.length).toFixed(2) + 'x';
        }
    } catch (error) {
        console.error("Gagal memuat data:", error);
    }
}

async function handleUpload(file) {
    if (!file.name.match(/\.(bmp|png)$/i)) {
        await showAlert('Hanya mendukung gambar .BMP atau .PNG untuk mencegah kompresi Lossy bawaan.');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);
    if (currentUser) {
        formData.append('user_id', currentUser.id);
    }

    dropZone.classList.add('hidden');
    progressContainer.classList.remove('hidden');
    progressFill.style.width = '30%';
    progressText.innerText = 'Membaca matriks piksel gambar...';
    
    setTimeout(() => {
        progressFill.style.width = '65%';
        progressText.innerText = 'Menjalankan Algoritma LZW...';
    }, 400);

    try {
        const response = await fetch(`${API_BASE_URL}/upload`, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) throw new Error("Gagal mengompresi");
        
        const result = await response.json();
        
        progressFill.style.width = '100%';
        progressText.innerText = 'Arsip Berhasil Disimpan!';
        
        const dbRecord = result.database_record;
        lastUploadedId = dbRecord.id;
        
        document.getElementById('compressionStats').innerHTML = 
            `Ukuran menyusut dari <strong>${formatBytes(dbRecord.original_size)}</strong> menjadi <strong>${formatBytes(dbRecord.compressed_size)}</strong>`;
        
        setTimeout(() => {
            progressContainer.classList.add('hidden');
            downloadZone.classList.remove('hidden');
            progressFill.style.width = '0%';
            loadDashboard(); 
        }, 1200);

    } catch (error) {
        await showAlert('Terjadi kesalahan saat kompresi! Pastikan Server Uvicorn menyala.');
        progressContainer.classList.add('hidden');
        dropZone.classList.remove('hidden');
    }
}

function downloadLast() {
    if (lastUploadedId) {
        window.open(`${API_BASE_URL}/download/${lastUploadedId}`);
    }
}

function resetUpload() {
    downloadZone.classList.add('hidden');
    dropZone.classList.remove('hidden');
    fileInput.value = '';
}

function showConfirm(message, isDanger = false) {
    return new Promise((resolve) => {
        const modal = document.getElementById('customModal');
        const modalText = document.getElementById('modalText');
        const btnOk = document.getElementById('modalBtnOk');
        const btnCancel = document.getElementById('modalBtnCancel');

        modalText.innerText = message;
        
        if (isDanger) {
            btnOk.classList.add('danger');
        } else {
            btnOk.classList.remove('danger');
        }
        
        modal.classList.remove('hidden');

        const cleanup = () => {
            modal.classList.add('hidden');
            btnOk.removeEventListener('click', onOk);
            btnCancel.removeEventListener('click', onCancel);
        };

        const onOk = () => {
            cleanup();
            resolve(true);
        };

        const onCancel = () => {
            cleanup();
            resolve(false);
        };

        btnOk.addEventListener('click', onOk);
        btnCancel.addEventListener('click', onCancel);
    });
}

function showAlert(message) {
    return new Promise((resolve) => {
        const modal = document.getElementById('customModal');
        const modalText = document.getElementById('modalText');
        const btnOk = document.getElementById('modalBtnOk');
        const btnCancel = document.getElementById('modalBtnCancel');
        const modalTitle = document.querySelector('#customModal .modal-title');

        modalTitle.innerText = 'Pemberitahuan';
        modalText.innerText = message;
        btnCancel.style.display = 'none'; // Sembunyikan cancel untuk alert
        modal.classList.remove('hidden');

        const cleanup = () => {
            modal.classList.add('hidden');
            btnOk.removeEventListener('click', onOk);
            btnCancel.style.display = 'block'; // Kembalikan ke normal
            modalTitle.innerText = 'Konfirmasi';
        };

        const onOk = () => {
            cleanup();
            resolve(true);
        };

        btnOk.addEventListener('click', onOk);
    });
}

async function deleteArchive(id) {
    const confirmed = await showConfirm('Yakin ingin menghapus arsip ini?', true);
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/archives/${id}`, {
            method: 'DELETE'
        });
        if (response.ok) {
            loadDashboard();
        }
    } catch (error) {
        await showAlert('Gagal menghapus arsip');
    }
}

async function deleteAllArchives() {
    const confirmed = await showConfirm('Yakin ingin menghapus SEMUA riwayat kompresi? Data tidak bisa dikembalikan.', true);
    if (!confirmed) return;
    
    try {
        const response = await fetch(`${API_BASE_URL}/api/archives`, {
            method: 'DELETE'
        });
        if (response.ok) {
            loadDashboard();
        }
    } catch (error) {
        await showAlert('Gagal menghapus semua arsip');
    }
}

// Check session on startup
document.addEventListener('DOMContentLoaded', () => {
    if (currentUser) {
        document.getElementById('dashboardSection').classList.remove('hidden');
        document.querySelector('.nav-right').innerHTML = `
            <div style="font-weight: 700; color: #333; margin-right: 20px; display: flex; align-items: center; gap: 5px;">
                <i class="ri-user-smile-fill" style="color: #4a90e2; font-size: 1.2rem;"></i> 
                ${currentUser.email.split('@')[0]}
            </div>
            <button class="btn-register" onclick="logout()">Keluar</button>
        `;
        loadDashboard();
    }
});

async function logout() {
    const confirmed = await showConfirm('Apakah Anda yakin mau keluar?', false);
    if (!confirmed) return;
    
    localStorage.removeItem('user');
    location.reload();
}

// Auth Modal Logic
const loginModal = document.getElementById('loginModal');
const registerModal = document.getElementById('registerModal');

function openLogin() {
    loginModal.classList.remove('hidden');
    registerModal.classList.add('hidden');
}

function openRegister() {
    registerModal.classList.remove('hidden');
    loginModal.classList.add('hidden');
}

function closeAuthModals() {
    loginModal.classList.add('hidden');
    registerModal.classList.add('hidden');
}

function switchModal(type) {
    if (type === 'login') {
        openLogin();
    } else {
        openRegister();
    }
}

async function handleAuth(e, type) {
    e.preventDefault();
    
    const form = e.target;
    const email = form.querySelector('input[type="email"]').value;
    const password = form.querySelector('input[type="password"]').value;
    
    let payload = { email, password };
    
    if (type === 'Daftar') {
        const fullName = form.querySelector('input[type="text"]').value;
        payload.full_name = fullName;
    }
    
    const endpoint = type === 'Daftar' ? '/api/auth/register' : '/api/auth/login';
    
    try {
        const res = await fetch(`${API_BASE_URL}${endpoint}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(payload)
        });
        
        const result = await res.json();
        
        if (result.status === 'success') {
            await showAlert(result.message);
            
            if (type === 'Daftar') {
                // Jangan langsung login, paksa ke form login
                switchModal('login');
                document.querySelector('#loginForm input[type="email"]').value = email;
            } else {
                closeAuthModals();
                
                currentUser = result.user;
                localStorage.setItem('user', JSON.stringify(currentUser));
                
                // Ubah Navbar menjadi Mode Login
                document.querySelector('.nav-right').innerHTML = `
                    <div style="font-weight: 700; color: #333; margin-right: 20px; display: flex; align-items: center; gap: 5px;">
                        <i class="ri-user-smile-fill" style="color: #4a90e2; font-size: 1.2rem;"></i> 
                        ${result.user.email.split('@')[0]}
                    </div>
                    <button class="btn-register" onclick="logout()">Keluar</button>
                `;
                
                document.getElementById('dashboardSection').classList.remove('hidden');
                loadDashboard();
            }
        } else {
            await showAlert(result.message);
        }
    } catch (error) {
        await showAlert('Terjadi kesalahan koneksi ke server.');
    }
}
