import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import * as GaussianSplats3D from '@mkkellogg/gaussian-splats-3d';

// Application State
let sceneData = null;
let currentFrameIdx = 0;
let isPlaying = false;
let playInterval = null;

// Three.js Globals
let scene, camera, renderer, controls;
let trajectoryLine, frustumGroup, currentCamMarker, plateMesh;
let dropInViewer = null;
let frustumMeshes = [];
let raycaster, mouse;

// WASD fly state (camera-relative; Q/E = down/up, Shift = fast)
const FLY_SPEED = 0.3; // m/s
const FLY_FAST_MULTIPLIER = 4;
const FLY_KEYS = ['KeyW', 'KeyA', 'KeyS', 'KeyD', 'KeyQ', 'KeyE'];
const flyKeys = new Set();
let flyFast = false;
let lastFrameTime = 0;

// Animation state
let isAnimatingCamera = false;
let animStartPos = new THREE.Vector3();
let animEndPos = new THREE.Vector3();
let animStartQuat = new THREE.Quaternion();
let animEndQuat = new THREE.Quaternion();
let animStartTime = 0;
let animDuration = 500; // ms

// Helper: Construct Three.js Matrix4 from 4x4 row-major array
function getC2WMatrix(c2wArray) {
    const m = new THREE.Matrix4();
    m.set(
        c2wArray[0][0], c2wArray[0][1], c2wArray[0][2], c2wArray[0][3],
        c2wArray[1][0], c2wArray[1][1], c2wArray[1][2], c2wArray[1][3],
        c2wArray[2][0], c2wArray[2][1], c2wArray[2][2], c2wArray[2][3],
        c2wArray[3][0], c2wArray[3][1], c2wArray[3][2], c2wArray[3][3]
    );
    return m;
}

// Helper: Convert OpenCV C2W (+X right, +Y down, +Z look) to Three.js Camera Pose (+X right, +Y up, -Z look)
function getThreeCameraPose(c2wArray) {
    const c2w = getC2WMatrix(c2wArray);
    const cv2three = new THREE.Matrix4().makeScale(1, -1, -1);
    const threeCamMat = c2w.clone().multiply(cv2three);
    const pos = new THREE.Vector3().setFromMatrixPosition(c2w);
    const quat = new THREE.Quaternion().setFromRotationMatrix(threeCamMat);
    const lookDir = new THREE.Vector3(c2wArray[0][2], c2wArray[1][2], c2wArray[2][2]).normalize();
    return { pos, quat, lookDir };
}

// Initialize App
async function init() {
    initThreeJS();
    initCurtainSlider();
    initUIEventListeners();

    try {
        const response = await fetch('scene_data.json');
        sceneData = await response.json();

        // Set camera vertical FOV based on calibrated camera intrinsics
        if (sceneData.intrinsics) {
            const h = sceneData.intrinsics.h || 480;
            const fy = sceneData.intrinsics.fy || 386.51;
            camera.fov = 2 * Math.atan((h / 2) / fy) * (180 / Math.PI);
            camera.updateProjectionMatrix();
        }

        populateCameraSelector();
        build3DScene();
        selectFrame(0, false);
        await loadSplatModel('model.splat');
    } catch (e) {
        console.error('Failed to load scene_data.json:', e);
    }
}

// 1. Setup Three.js 3D Viewport
function initThreeJS() {
    const container = document.getElementById('threejs-canvas-wrapper');
    const width = container.clientWidth;
    const height = container.clientHeight;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060913);

    // Initial overview perspective
    camera = new THREE.PerspectiveCamera(55, width / height, 0.01, 50);
    camera.up.set(0, -1, 0); // World Up is -Y (orthogonal to +Z look direction)
    camera.position.set(0.6, -0.6, -0.8);

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0.6, 0.0, 0.2);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 1.2);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0x38bdf8, 1.0);
    dirLight.position.set(2, -2, -2);
    scene.add(dirLight);

    // Coordinate Grid Helper (horizontal ground grid below the robot, low opacity)
    const gridHelper = new THREE.GridHelper(4, 20, 0x0ea5e9, 0x1e293b);
    gridHelper.position.set(0.6, 0.25, 0.10);
    gridHelper.material.transparent = true;
    gridHelper.material.opacity = 0.2;
    scene.add(gridHelper);

    // Raycaster for clicking camera frustums in 3D
    raycaster = new THREE.Raycaster();
    mouse = new THREE.Vector2();

    renderer.domElement.addEventListener('pointerdown', onDocumentPointerDown, false);
    window.addEventListener('resize', onWindowResize, false);

    requestAnimationFrame(renderLoop);
}

function onWindowResize() {
    const container = document.getElementById('threejs-canvas-wrapper');
    if (!container) return;
    camera.aspect = container.clientWidth / container.clientHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(container.clientWidth, container.clientHeight);
}

// 2. Build 3D Trajectory & Camera Frustums
function build3DScene() {
    if (!sceneData || !sceneData.frames) return;

    // A. Trajectory Line
    const trajPoints = [];
    sceneData.frames.forEach(fr => {
        const c2w = getC2WMatrix(fr.c2w);
        const pos = new THREE.Vector3().setFromMatrixPosition(c2w);
        trajPoints.push(pos);
    });

    const trajGeo = new THREE.BufferGeometry().setFromPoints(trajPoints);
    const trajMat = new THREE.LineBasicMaterial({ color: 0x06b6d4, linewidth: 2 });
    trajectoryLine = new THREE.Line(trajGeo, trajMat);
    scene.add(trajectoryLine);

    // B. Camera Frustum Pyramids
    frustumGroup = new THREE.Group();
    frustumMeshes = [];

    const fov = 55 * Math.PI / 180;
    const aspect = 640 / 480;
    const scale = 0.05; // Pyramid size

    sceneData.frames.forEach((fr, i) => {
        // Wireframe pyramid pointing along +Z (OpenCV camera look direction)
        const wireGeo = createCameraFrustumGeometry(fov, aspect, scale);
        const wireColor = fr.is_val ? 0x10b981 : 0x3b82f6;
        const wireMat = new THREE.LineBasicMaterial({ 
            color: wireColor, 
            transparent: true, 
            opacity: fr.is_val ? 0.9 : 0.35 
        });
        const frustum = new THREE.LineSegments(wireGeo, wireMat);

        const c2w = getC2WMatrix(fr.c2w);
        frustum.applyMatrix4(c2w);
        frustum.userData = { frameIndex: i, isVal: fr.is_val };

        frustumGroup.add(frustum);
        frustumMeshes.push(frustum);
    });

    scene.add(frustumGroup);

    // C. Current Active Camera Marker (Bright Amber)
    const markerGeo = createCameraFrustumGeometry(fov, aspect, scale * 1.4);
    const markerMat = new THREE.LineBasicMaterial({ color: 0xf59e0b, linewidth: 3 });
    currentCamMarker = new THREE.LineSegments(markerGeo, markerMat);
    currentCamMarker.matrixAutoUpdate = false;
    scene.add(currentCamMarker);
}

function createCameraFrustumGeometry(fov, aspect, depth) {
    const halfH = Math.tan(fov / 2) * depth;
    const halfW = halfH * aspect;

    const vertices = new Float32Array([
        0, 0, 0,   -halfW, -halfH, depth,
        0, 0, 0,    halfW, -halfH, depth,
        0, 0, 0,    halfW,  halfH, depth,
        0, 0, 0,   -halfW,  halfH, depth,
        -halfW, -halfH, depth,   halfW, -halfH, depth,
         halfW, -halfH, depth,   halfW,  halfH, depth,
         halfW,  halfH, depth,  -halfW,  halfH, depth,
        -halfW,  halfH, depth,  -halfW, -halfH, depth
    ]);

    const geo = new THREE.BufferGeometry();
    geo.setAttribute('position', new THREE.BufferAttribute(vertices, 3));
    return geo;
}

// 2.5 Load and Render 3D Gaussian Splats via DropInViewer
async function loadSplatModel(filename = 'model.splat') {
    const label = document.getElementById('splats-label');
    if (label) label.textContent = '⏳ Loading 3D Gaussian Splats...';

    try {
        if (dropInViewer) {
            scene.remove(dropInViewer);
            if (dropInViewer.viewer) {
                dropInViewer.viewer.dispose();
            }
            dropInViewer = null;
        }

        dropInViewer = new GaussianSplats3D.DropInViewer({
            // GPU sort skips uploading splat centers to the sort worker, which then clamps
            // its render count to 0 uploaded splats -> instanceCount stays 0 and nothing draws.
            gpuAcceleratedSort: false,
            sharedMemoryForWorkers: false
        });
        scene.add(dropInViewer);

        // Cache-bust: python http.server sends no Cache-Control, so regenerated .splat files
        // would otherwise be served stale. Query string hides the extension, so set format explicitly.
        await dropInViewer.addSplatScene(`${filename}?v=${Date.now()}`, {
            format: GaussianSplats3D.SceneFormat.Splat,
            splatAlphaRemovalThreshold: 5,
            showLoadingUI: false
        });

        const toggle = document.getElementById('toggle-splats');
        if (toggle) dropInViewer.visible = toggle.checked;

        const drawn = dropInViewer.viewer.splatMesh.getSplatCount();
        if (label) label.textContent = `✨ 3D Gaussian Splats (${drawn.toLocaleString()})`;
        console.log(`Successfully loaded 3D Gaussian Splatting scene: ${filename} (${drawn} splats)`);
    } catch (err) {
        console.error('Failed to load splat model with DropInViewer:', err);
        if (label) label.textContent = '⚠️ Splats Render Fallback';
    }
}

// 3. Click Raycaster
function onDocumentPointerDown(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(frustumMeshes, true);

    if (intersects.length > 0) {
        let hit = intersects[0].object;
        while (hit && hit.userData.frameIndex === undefined && hit.parent) {
            hit = hit.parent;
        }
        if (hit && hit.userData.frameIndex !== undefined) {
            selectFrame(hit.userData.frameIndex, true);
        }
    }
}

// 4. Camera Snapping & Smooth Fly-In
function snapCameraToCurrentFrame() {
    if (!sceneData || !sceneData.frames[currentFrameIdx]) return;

    const fr = sceneData.frames[currentFrameIdx];
    const { pos, quat, lookDir } = getThreeCameraPose(fr.c2w);

    animStartPos.copy(camera.position);
    animStartQuat.copy(camera.quaternion);

    animEndPos.copy(pos);
    animEndQuat.copy(quat);

    // Target point directly ahead along camera optical axis (+Z_cv) into the weld seam
    const target = pos.clone().addScaledVector(lookDir, 0.20);
    controls.target.copy(target);

    // Hide active camera marker and frustum when snapped so it doesn't block the camera lens
    if (currentCamMarker) currentCamMarker.visible = false;
    frustumMeshes.forEach((m, i) => {
        m.visible = (i !== currentFrameIdx);
    });

    animStartTime = performance.now();
    isAnimatingCamera = true;
}

// Translate camera and orbit target together so mouse orbiting still works after flying
function applyFlyMovement(dt) {
    const move = new THREE.Vector3(
        (flyKeys.has('KeyD') ? 1 : 0) - (flyKeys.has('KeyA') ? 1 : 0),
        (flyKeys.has('KeyE') ? 1 : 0) - (flyKeys.has('KeyQ') ? 1 : 0),
        (flyKeys.has('KeyS') ? 1 : 0) - (flyKeys.has('KeyW') ? 1 : 0) // camera looks down -Z
    );
    if (move.lengthSq() === 0) return;
    const speed = FLY_SPEED * (flyFast ? FLY_FAST_MULTIPLIER : 1);
    move.normalize().multiplyScalar(speed * dt).applyQuaternion(camera.quaternion);
    camera.position.add(move);
    controls.target.add(move);
}

function renderLoop(time) {
    requestAnimationFrame(renderLoop);

    const dt = Math.min((time - lastFrameTime) / 1000, 0.1);
    lastFrameTime = time;

    if (flyKeys.size > 0) {
        isAnimatingCamera = false; // manual flight cancels a snap animation
        applyFlyMovement(dt);
    }

    if (isAnimatingCamera) {
        const elapsed = time - animStartTime;
        const progress = Math.min(elapsed / animDuration, 1.0);
        const ease = 0.5 - 0.5 * Math.cos(progress * Math.PI); // easeInOutSine

        camera.position.lerpVectors(animStartPos, animEndPos, ease);
        camera.quaternion.slerpQuaternions(animStartQuat, animEndQuat, ease);

        if (progress >= 1.0) {
            isAnimatingCamera = false;
            camera.position.copy(animEndPos);
            camera.quaternion.copy(animEndQuat);
            if (sceneData && sceneData.frames[currentFrameIdx]) {
                const fr = sceneData.frames[currentFrameIdx];
                const { pos, lookDir } = getThreeCameraPose(fr.c2w);
                controls.target.copy(pos.clone().addScaledVector(lookDir, 0.25));
            }
        }
    } else {
        controls.update();
    }

    renderer.render(scene, camera);
}

// 5. Populate Frame Selector Dropdown
function populateCameraSelector() {
    const select = document.getElementById('camera-select');
    select.innerHTML = '';

    // First group: Validation frames
    const valOptGroup = document.createElement('optgroup');
    valOptGroup.label = '── Validation Frames (Held-out Test) ──';

    const trainOptGroup = document.createElement('optgroup');
    trainOptGroup.label = '── Training Frames ──';

    sceneData.frames.forEach((fr, i) => {
        const opt = document.createElement('option');
        opt.value = i;
        if (fr.is_val) {
            opt.textContent = `★ Frame ${fr.file_name} (Val Test #${fr.val_idx})`;
            valOptGroup.appendChild(opt);
        } else {
            opt.textContent = `Frame ${fr.file_name}`;
            trainOptGroup.appendChild(opt);
        }
    });

    select.appendChild(valOptGroup);
    select.appendChild(trainOptGroup);

    // Timeline Slider Range
    const slider = document.getElementById('timeline-slider');
    slider.min = 0;
    slider.max = sceneData.frames.length - 1;
    slider.value = 0;
}

// 6. Select Frame
function selectFrame(idx, snap = false) {
    if (!sceneData || idx < 0 || idx >= sceneData.frames.length) return;
    currentFrameIdx = idx;

    const fr = sceneData.frames[idx];

    // Update Dropdown & Slider
    const camSelect = document.getElementById('camera-select');
    if (camSelect) camSelect.value = idx;
    const timeSlider = document.getElementById('timeline-slider');
    if (timeSlider) timeSlider.value = idx;
    const timeCurrent = document.getElementById('time-current');
    if (timeCurrent) timeCurrent.textContent = `Frame ${idx}: ${fr.file_name}`;

    // Update Telemetry Panel
    const telId = document.getElementById('tel-id');
    if (telId) telId.textContent = `#${idx}${fr.is_val ? ' (Val Test #' + fr.val_idx + ')' : ''}`;
    const telTime = document.getElementById('tel-time');
    if (telTime) telTime.textContent = `${(idx * 0.1).toFixed(2)} s`;
    const telX = document.getElementById('tel-x');
    if (telX) telX.textContent = `${fr.c2w[0][3] >= 0 ? '+' : ''}${fr.c2w[0][3].toFixed(3)} m`;
    const telY = document.getElementById('tel-y');
    if (telY) telY.textContent = `${fr.c2w[1][3] >= 0 ? '+' : ''}${fr.c2w[1][3].toFixed(3)} m`;
    const telZ = document.getElementById('tel-z');
    if (telZ) telZ.textContent = `${fr.c2w[2][3] >= 0 ? '+' : ''}${fr.c2w[2][3].toFixed(3)} m`;
    const telDist = document.getElementById('tel-dist');
    if (telDist) telDist.textContent = `~${((0.18 - fr.c2w[2][3]) * 100).toFixed(1)} cm`;

    // Update Active Camera Frustum Marker
    if (currentCamMarker) {
        const c2w = getC2WMatrix(fr.c2w);
        currentCamMarker.matrix.copy(c2w);
    }

    // Update Frustum Colors in Viewport
    frustumMeshes.forEach((mesh, i) => {
        if (i === idx) {
            mesh.material.color.setHex(0xf59e0b); // Active Gold
            mesh.material.opacity = 1.0;
        } else {
            mesh.material.color.setHex(mesh.userData.isVal ? 0x10b981 : 0x3b82f6);
            mesh.material.opacity = mesh.userData.isVal ? 0.9 : 0.35;
        }
    });

    // Update Images in Comparison Panel
    updateComparisonImages(fr);

    if (snap) {
        snapCameraToCurrentFrame();
    }
}

// gsplat eval PNGs are a [GT | render] canvas (canvas_list = [pixels, colors]); keep only the render half
let renderRequestId = 0;
function setRenderImage(imgEls, path) {
    const requestId = ++renderRequestId;
    const src = new Image();
    src.onload = () => {
        if (requestId !== renderRequestId) return; // a newer frame was selected meanwhile
        const w = src.naturalWidth / 2;
        const canvas = document.createElement('canvas');
        canvas.width = w;
        canvas.height = src.naturalHeight;
        canvas.getContext('2d').drawImage(src, w, 0, w, src.naturalHeight, 0, 0, w, src.naturalHeight);
        const url = canvas.toDataURL('image/png');
        imgEls.forEach(el => { el.src = url; });
    };
    src.src = path;
}

function updateComparisonImages(fr) {
    const method = document.getElementById('compare-method-select').value;
    const gtImgPath = `gt_images/${fr.file_name}`;

    // Renders exist for validation frames
    let renderImgPath = '';
    let isRenderAvailable = fr.is_val;

    if (fr.is_val) {
        if (method === 'baseline') {
            renderImgPath = `baseline_renders/val_step14999_${String(fr.val_idx).padStart(4, '0')}.png`;
        } else {
            // Bilateral render
            renderImgPath = `bilateral_renders/val_step14999_${String(fr.val_idx).padStart(4, '0')}.png`;
        }
    }

    // Set GT images
    const imgGT = document.getElementById('img-gt');
    const imgSideGT = document.getElementById('img-side-gt');
    imgGT.src = gtImgPath;
    imgSideGT.src = gtImgPath;

    // Set Rendered images
    const imgRendered = document.getElementById('img-rendered');
    const imgSideRender = document.getElementById('img-side-render');

    if (isRenderAvailable) {
        setRenderImage([imgRendered, imgSideRender], renderImgPath);
        document.getElementById('curtain-container').style.display = 'block';
    } else {
        // Training frame (or no render yet)
        renderRequestId++;
        imgRendered.src = gtImgPath;
        imgSideRender.src = gtImgPath;
        document.getElementById('side-render-title').textContent = 'Training View (No Test Render)';
    }

    // Update Diagnostics
    if (fr.is_val) {
        if (method === 'baseline') {
            document.getElementById('metric-psnr').textContent = '22.02 dB';
            document.getElementById('metric-ssim').textContent = '0.799';
            document.getElementById('side-render-title').textContent = 'Baseline 3DGS (Static SH)';
            document.getElementById('insight-text').innerHTML = '<strong>Baseline 3DGS Limitation:</strong> Static spherical harmonics cannot model the headlight attached to the crawler. Specular glare is averaged into a blurry diffuse wash.';
        } else {
            document.getElementById('metric-psnr').textContent = '21.02 dB';
            document.getElementById('metric-ssim').textContent = '0.795';
            document.getElementById('side-render-title').textContent = 'Illumination-Aware 3DGS';
            document.getElementById('insight-text').innerHTML = '<strong>Bilateral Grid Compensation:</strong> Per-frame 3D grid captures non-linear illumination falloff and specular highlights, keeping surface micro-texture sharp.';
        }
    } else {
        document.getElementById('metric-psnr').textContent = 'N/A (Train)';
        document.getElementById('metric-ssim').textContent = 'N/A';
    }
}

// 7. Interactive Split Curtain Slider
function initCurtainSlider() {
    const wrapper = document.querySelector('.curtain-wrapper');
    const container = document.getElementById('curtain-container');
    const handle = document.getElementById('curtain-handle');
    let isDragging = false;

    function updateCurtain(x) {
        const rect = wrapper.getBoundingClientRect();
        let pos = (x - rect.left) / rect.width;
        pos = Math.max(0, Math.min(pos, 1));
        const pct = pos * 100;

        container.style.clipPath = `inset(0 ${100 - pct}% 0 0)`;
        handle.style.left = `${pct}%`;
    }

    wrapper.addEventListener('pointerdown', (e) => {
        isDragging = true;
        updateCurtain(e.clientX);
    });

    window.addEventListener('pointermove', (e) => {
        if (!isDragging) return;
        updateCurtain(e.clientX);
    });

    window.addEventListener('pointerup', () => {
        isDragging = false;
    });
}

// 8. UI Event Listeners
function initUIEventListeners() {
    document.getElementById('camera-select').addEventListener('change', (e) => {
        selectFrame(parseInt(e.target.value), false);
    });

    document.getElementById('timeline-slider').addEventListener('input', (e) => {
        selectFrame(parseInt(e.target.value), false);
    });

    document.getElementById('btn-snap').addEventListener('click', () => {
        snapCameraToCurrentFrame();
    });

    document.getElementById('btn-reset-view').addEventListener('click', () => {
        animStartPos.copy(camera.position);
        animStartQuat.copy(camera.quaternion);
        animEndPos.set(0.6, -0.6, -0.8);
        controls.target.set(0.6, 0.0, 0.2);
        const lookMat = new THREE.Matrix4().lookAt(animEndPos, controls.target, new THREE.Vector3(0, -1, 0));
        animEndQuat.setFromRotationMatrix(lookMat);
        animStartTime = performance.now();
        isAnimatingCamera = true;
    });

    document.getElementById('btn-prev').addEventListener('click', () => {
        selectFrame(Math.max(0, currentFrameIdx - 1), false);
    });

    document.getElementById('btn-next').addEventListener('click', () => {
        if (sceneData) {
            selectFrame(Math.min(sceneData.frames.length - 1, currentFrameIdx + 1), false);
        }
    });

    // WASD fly controls for the 3D viewport
    const isTextField = (el) => el.tagName === 'TEXTAREA' || (el.tagName === 'INPUT' && el.type === 'text');
    window.addEventListener('keydown', (e) => {
        flyFast = e.shiftKey;
        if (!FLY_KEYS.includes(e.code) || isTextField(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
        e.preventDefault(); // stop <select> type-ahead from changing the frame
        flyKeys.add(e.code);
    });
    window.addEventListener('keyup', (e) => {
        flyFast = e.shiftKey;
        flyKeys.delete(e.code);
    });
    window.addEventListener('blur', () => flyKeys.clear());

    // Keyboard Arrow navigation
    window.addEventListener('keydown', (e) => {
        if (e.key === 'ArrowLeft') {
            selectFrame(Math.max(0, currentFrameIdx - 1), false);
        } else if (e.key === 'ArrowRight') {
            if (sceneData) {
                selectFrame(Math.min(sceneData.frames.length - 1, currentFrameIdx + 1), false);
            }
        } else if (e.key === ' ' || e.key === 'Spacebar') {
            togglePlay();
        }
    });

    // Play / Pause
    document.getElementById('btn-play').addEventListener('click', togglePlay);

    function togglePlay() {
        isPlaying = !isPlaying;
        const btn = document.getElementById('btn-play');
        if (isPlaying) {
            btn.textContent = '⏸ Pause';
            btn.classList.add('btn-highlight');
            playInterval = setInterval(() => {
                if (!sceneData) return;
                const next = (currentFrameIdx + 1) % sceneData.frames.length;
                selectFrame(next, false);
            }, 100);
        } else {
            btn.textContent = '▶ Play';
            btn.classList.remove('btn-highlight');
            clearInterval(playInterval);
        }
    }

    // View Mode Tabs
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            const mode = e.target.getAttribute('data-mode');
            if (mode === 'split') {
                document.getElementById('split-curtain-view').classList.add('active');
                document.getElementById('side-by-side-view').classList.remove('active');
            } else {
                document.getElementById('split-curtain-view').classList.remove('active');
                document.getElementById('side-by-side-view').classList.add('active');
            }
        });
    });

    // Method Select (Baseline vs Bilateral)
    document.getElementById('compare-method-select').addEventListener('change', () => {
        if (sceneData) {
            updateComparisonImages(sceneData.frames[currentFrameIdx]);
        }
    });

    // Layer Toggles
    document.getElementById('toggle-splats')?.addEventListener('change', (e) => {
        if (dropInViewer) dropInViewer.visible = e.target.checked;
        const sub = document.getElementById('splat-sub-controls');
        if (sub) sub.style.display = e.target.checked ? 'flex' : 'none';
    });

    document.getElementById('splat-model-select')?.addEventListener('change', (e) => {
        loadSplatModel(e.target.value);
    });

    document.getElementById('splat-size-slider')?.addEventListener('input', (e) => {
        const val = parseFloat(e.target.value);
        if (dropInViewer && dropInViewer.viewer && dropInViewer.viewer.splatMesh) {
            dropInViewer.viewer.splatMesh.setSplatScale(val * 80.0);
        }
        const valLabel = document.getElementById('splat-size-val');
        if (valLabel) valLabel.textContent = val.toFixed(3);
    });

    document.getElementById('toggle-frustums').addEventListener('change', (e) => {
        if (frustumGroup) frustumGroup.visible = e.target.checked;
    });

    document.getElementById('toggle-trajectory').addEventListener('change', (e) => {
        if (trajectoryLine) trajectoryLine.visible = e.target.checked;
    });

    document.getElementById('toggle-plate').addEventListener('change', (e) => {
        if (plateMesh) plateMesh.visible = e.target.checked;
    });
}

// Start
init();
