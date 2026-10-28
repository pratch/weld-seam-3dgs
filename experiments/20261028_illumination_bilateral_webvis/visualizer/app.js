import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Application State
let sceneData = null;
let currentFrameIdx = 0;
let isPlaying = false;
let playInterval = null;

// Three.js Globals
let scene, camera, renderer, controls;
let trajectoryLine, frustumGroup, currentCamMarker, plateMesh;
let frustumMeshes = [];
let raycaster, mouse;

// Animation state
let isAnimatingCamera = false;
let animStartPos = new THREE.Vector3();
let animEndPos = new THREE.Vector3();
let animStartQuat = new THREE.Quaternion();
let animEndQuat = new THREE.Quaternion();
let animStartTime = 0;
let animDuration = 600; // ms

// Initialize App
async function init() {
    initThreeJS();
    initCurtainSlider();
    initUIEventListeners();

    try {
        const response = await fetch('scene_data.json');
        sceneData = await response.json();
        populateCameraSelector();
        build3DScene();
        selectFrame(0, true);
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
    scene.background = new THREE.Color(0x050811);
    scene.fog = new THREE.FogExp2(0x050811, 0.2);

    camera = new THREE.PerspectiveCamera(50, width / height, 0.01, 100);
    camera.position.set(0.6, -1.8, 1.2);
    camera.up.set(0, 0, 1); // Z-up world

    renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(width, height);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    container.appendChild(renderer.domElement);

    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.05;
    controls.target.set(0.6, 0.0, 0.1);

    // Lights
    const ambientLight = new THREE.AmbientLight(0xffffff, 0.8);
    scene.add(ambientLight);

    const dirLight = new THREE.DirectionalLight(0x06b6d4, 1.5);
    dirLight.position.set(2, -3, 4);
    scene.add(dirLight);

    // Coordinate Grid Helper (aligned with steel wall at Z=0.15)
    const gridHelper = new THREE.GridHelper(6, 30, 0x06b6d4, 0x1e293b);
    gridHelper.rotation.x = Math.PI / 2;
    gridHelper.position.set(0.6, 0, 0.15);
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
        const mat = new THREE.Matrix4().fromArray(fr.c2w.flat());
        const pos = new THREE.Vector3().setFromMatrixPosition(mat);
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
    const scale = 0.06; // Pyramid size

    sceneData.frames.forEach((fr, i) => {
        // Frustum wireframe
        const wireGeo = createCameraFrustumGeometry(fov, aspect, scale);
        const wireColor = fr.is_val ? 0x10b981 : 0x3b82f6;
        const wireMat = new THREE.LineBasicMaterial({ 
            color: wireColor, 
            transparent: true, 
            opacity: fr.is_val ? 0.9 : 0.35 
        });
        const frustum = new THREE.LineSegments(wireGeo, wireMat);

        const mat = new THREE.Matrix4().fromArray(fr.c2w.flat());
        frustum.applyMatrix4(mat);
        frustum.userData = { frameIndex: i, isVal: fr.is_val };

        frustumGroup.add(frustum);
        frustumMeshes.push(frustum);
    });

    scene.add(frustumGroup);

    // C. Current Active Camera Marker (Bright Amber)
    const markerGeo = createCameraFrustumGeometry(fov, aspect, scale * 1.4);
    const markerMat = new THREE.LineBasicMaterial({ color: 0xf59e0b, linewidth: 3 });
    currentCamMarker = new THREE.LineSegments(markerGeo, markerMat);
    scene.add(currentCamMarker);

    // D. Vessel Plate Guide (Wall representation)
    const plateGeo = new THREE.PlaneGeometry(3.5, 0.8);
    const plateMat = new THREE.MeshStandardMaterial({
        color: 0x1f2937,
        roughness: 0.8,
        metalness: 0.2,
        side: THREE.DoubleSide
    });
    plateMesh = new THREE.Mesh(plateGeo, plateMat);
    plateMesh.position.set(0.6, 0.0, 0.16); // ~15 cm from camera
    scene.add(plateMesh);
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

// 3. Click Raycaster
function onDocumentPointerDown(event) {
    const rect = renderer.domElement.getBoundingClientRect();
    mouse.x = ((event.clientX - rect.left) / rect.width) * 2 - 1;
    mouse.y = -((event.clientY - rect.top) / rect.height) * 2 + 1;

    raycaster.setFromCamera(mouse, camera);
    const intersects = raycaster.intersectObjects(frustumMeshes, true);

    if (intersects.length > 0) {
        const hit = intersects[0].object;
        if (hit.userData && hit.userData.frameIndex !== undefined) {
            selectFrame(hit.userData.frameIndex);
        }
    }
}

// 4. Camera Snapping & Smooth Fly-In
function snapCameraToCurrentFrame() {
    if (!sceneData || !sceneData.frames[currentFrameIdx]) return;

    const fr = sceneData.frames[currentFrameIdx];
    const mat = new THREE.Matrix4().fromArray(fr.c2w.flat());

    animStartPos.copy(camera.position);
    animStartQuat.copy(camera.quaternion);

    // Camera pose target
    animEndPos.setFromMatrixPosition(mat);
    animEndQuat.setFromRotationMatrix(mat);

    // Update orbit controls target slightly in front (+Z in OpenCV camera)
    const forward = new THREE.Vector3(0, 0, 0.4).applyMatrix4(mat);
    controls.target.copy(forward);

    animStartTime = performance.now();
    isAnimatingCamera = true;
}

function renderLoop(time) {
    requestAnimationFrame(renderLoop);

    if (isAnimatingCamera) {
        const elapsed = time - animStartTime;
        const progress = Math.min(elapsed / animDuration, 1.0);
        const ease = 0.5 - 0.5 * Math.cos(progress * Math.PI); // easeInOutSine

        camera.position.lerpVectors(animStartPos, animEndPos, ease);
        camera.quaternion.slerpQuaternions(animStartQuat, animEndQuat, ease);

        if (progress >= 1.0) {
            isAnimatingCamera = false;
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
            opt.textContent = `★ Test Frame #${fr.val_idx} (Seq Frame ${i})`;
            valOptGroup.appendChild(opt);
        } else {
            opt.textContent = `Frame ${i}`;
            trainOptGroup.appendChild(opt);
        }
    });

    select.appendChild(valOptGroup);
    select.appendChild(trainOptGroup);

    document.getElementById('timeline-slider').max = sceneData.frames.length - 1;
    document.getElementById('time-total').textContent = `Frame ${sceneData.frames.length - 1}`;
}

// 6. Frame Selection & Image Sync
function selectFrame(idx, snap = false) {
    if (!sceneData || idx < 0 || idx >= sceneData.frames.length) return;
    currentFrameIdx = idx;

    const fr = sceneData.frames[idx];
    document.getElementById('camera-select').value = idx;
    document.getElementById('timeline-slider').value = idx;
    document.getElementById('time-current').textContent = `Frame ${idx}`;

    // Update active marker in 3D
    if (currentCamMarker) {
        const mat = new THREE.Matrix4().fromArray(fr.c2w.flat());
        currentCamMarker.position.set(0, 0, 0);
        currentCamMarker.rotation.set(0, 0, 0);
        currentCamMarker.scale.set(1, 1, 1);
        currentCamMarker.applyMatrix4(mat);
    }

    // Update Telemetry
    const mat = new THREE.Matrix4().fromArray(fr.c2w.flat());
    const pos = new THREE.Vector3().setFromMatrixPosition(mat);
    document.getElementById('tel-id').textContent = fr.is_val ? `#${idx} (Val ${fr.val_idx})` : `#${idx}`;
    document.getElementById('tel-time').textContent = `${fr.timestamp.toFixed(2)} s`;
    document.getElementById('tel-x').textContent = `${pos.x >= 0 ? '+' : ''}${pos.x.toFixed(3)} m`;
    document.getElementById('tel-y').textContent = `${pos.y >= 0 ? '+' : ''}${pos.y.toFixed(3)} m`;
    document.getElementById('tel-z').textContent = `${pos.z >= 0 ? '+' : ''}${pos.z.toFixed(3)} m`;

    // Distance to plate (Z ~ 0.16)
    const dist = Math.abs(pos.z - 0.16) * 100;
    document.getElementById('tel-dist').textContent = `~${dist.toFixed(1)} cm`;

    // Update Images in Comparison Panel
    updateComparisonImages(fr);

    if (snap) {
        snapCameraToCurrentFrame();
    }
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
        imgRendered.src = renderImgPath;
        imgSideRender.src = renderImgPath;
        document.getElementById('curtain-container').style.display = 'block';
    } else {
        // Training frame (or no render yet)
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
            document.getElementById('metric-psnr').textContent = 'Training...';
            document.getElementById('metric-ssim').textContent = 'Bilateral Grid';
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

        container.style.width = `${pct}%`;
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
        animEndPos.set(0.6, -1.8, 1.2);
        controls.target.set(0.6, 0.0, 0.1);
        const lookMat = new THREE.Matrix4().lookAt(animEndPos, controls.target, new THREE.Vector3(0, 0, 1));
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
