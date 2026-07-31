function MultiRigidBodyTracker()
% MULTIRIGIDBODYTRACKER
%
% Live multi-Rigid-Body tracking via OptiTrack Motive / NatNet.
% Modified for robust saving directly to Workspace and Disk.

    %% ---- Configuration ----
    DANGER_THRESHOLD_MM      = 100;
    WARNING_THRESHOLD_MM     = 500;
    MIN_APPROACH_SPEED_MMPS  = 20;
    STATIC_POSITION_RANGE_MM = 5;
    STATIC_EULER_RANGE_DEG   = 2;
    INITIAL_BUFFER_CAPACITY  = 2000;

    outputFolder = ['MocapSession_' datestr(now, 'yyyymmdd_HHMMSS')];
    mkdir(outputFolder);

    fprintf('Multi-Rigid-Body NatNet Tracker - Start\n');
    fprintf('=========================================================\n');

    %% 1. NatNet initialization
    natnetclient = connectToNatNet();

    %% 2. Rigid Body identification
    [idToName, rbNames] = buildRigidBodyMap(natnetclient);
    numRB = numel(rbNames);
    fprintf('Detected %d Rigid Body/Bodies from Motive:\n', numRB);
    for i = 1:numRB
        fprintf('   - %s\n', rbNames{i});
    end

    %% 3. Interactive selection
    selectedNames = selectRigidBodiesToRecord(rbNames);
    if isempty(selectedNames)
        fprintf('No Rigid Bodies selected -- nothing to record. Exiting.\n');
        natnetclient.disconnect;
        return;
    end

    %% 4. Pre-allocated data buffers + live plots
    Buffers = initializeBuffers(selectedNames, INITIAL_BUFFER_CAPACITY);
    [figHandle, plotHandles, combinedHandles] = initializePlots(selectedNames);
    setappdata(figHandle, 'stopRequested', false);
    uicontrol(figHandle, 'Style', 'pushbutton', 'String', 'STOP && SAVE', ...
        'FontSize', 13, 'FontWeight', 'bold', 'BackgroundColor', [0.85 0.2 0.2], ...
        'ForegroundColor', [1 1 1], 'Units', 'normalized', 'Position', [0.40 0.01 0.20 0.055], ...
        'Callback', @(src, evt) setappdata(figHandle, 'stopRequested', true));

    loopBufCapacity = INITIAL_BUFFER_CAPACITY;
    loopBufCount = 0;
    loopTimeBuf = NaN(loopBufCapacity, 1);

    %% 5. Receive Frame loop
    fprintf('\nStreaming... click the STOP && SAVE button in the figure (or close\n');
    fprintf('the window) to stop and save. Please avoid Ctrl+C.\n\n');
    startTime = tic;

    % Loop breaks naturally if figure is closed or STOP is clicked
    while ishandle(figHandle) && ~getappdata(figHandle, 'stopRequested')
        frame = natnetclient.getFrame;

        if isempty(frame)
            pause(0.001);
            continue;
        end

        try
            numRBInFrame = frame.nRigidBodies;
        catch
            pause(0.001);
            continue;
        end

        if numRBInFrame == 0
            pause(0.001);
            continue;
        end

        t = toc(startTime);

        loopBufCount = loopBufCount + 1;
        if loopBufCount > loopBufCapacity
            loopBufCapacity = loopBufCapacity * 2;
            loopTimeBuf(end+1:loopBufCapacity, 1) = NaN;
        end
        loopTimeBuf(loopBufCount) = t;

        seenThisFrame = false(1, numel(selectedNames));

        for k = 1:numRBInFrame
            try
                rb = frame.RigidBodies(k);
            catch indexErr
                fprintf(['WARNING: frame.nRigidBodies reported %d, but ' ...
                          'indexing frame.RigidBodies(%d) failed (%s). ' ...
                          'Skipping this entry.\n'], numRBInFrame, k, indexErr.message);
                continue
            end
            rbID = getRigidBodyID(rb);

            if ~isKey(idToName, rbID)
                [idToName, ~] = buildRigidBodyMap(natnetclient);
                continue
            end

            name = idToName(rbID);
            selIdx = find(strcmp(selectedNames, name), 1);
            if isempty(selIdx)
                continue 
            end
            seenThisFrame(selIdx) = true;

            [roll, pitch, yaw] = quaternionToEuler(double(rb.qx), double(rb.qy), double(rb.qz), double(rb.qw));
            positionMM = double([rb.x, rb.y, rb.z]) * 1000; 
            quat = double([rb.qx, rb.qy, rb.qz, rb.qw]);

            fieldName = matlab.lang.makeValidName(name);
            Buffers.(fieldName) = appendRow(Buffers.(fieldName), t, positionMM, quat, [roll, pitch, yaw]);

            if isfield(plotHandles, fieldName)
                addpoints(plotHandles.(fieldName).Traj3D, positionMM(1), positionMM(2), positionMM(3));
            end
            if isfield(combinedHandles, fieldName)
                addpoints(combinedHandles.(fieldName), positionMM(1), positionMM(2), positionMM(3));
            end
        end

        for si = 1:numel(selectedNames)
            if ~seenThisFrame(si)
                fn = matlab.lang.makeValidName(selectedNames{si});
                Buffers.(fn) = appendNaNRow(Buffers.(fn), t);
            end
        end

        drawnow limitrate;
    end

    %% ====================================================================
    %% 6. DISCONNECT AND BEGIN SEQUENTIAL SAVE
    %% ====================================================================
    fprintf('=========================================================\n');
    fprintf('Figure closed or STOP requested. Disconnecting...\n');
    try
        natnetclient.disconnect;
    catch
        % ignore
    end

    if ~exist('Buffers', 'var') || isempty(selectedNames) || loopBufCount == 0
        fprintf('No frames were captured -- skipping analysis and save.\n');
        return;
    end

    %% Trim buffers -> OriginalData (raw, always kept complete)
    OriginalData = struct();
    for si2 = 1:numel(selectedNames)
        fn2 = matlab.lang.makeValidName(selectedNames{si2});
        OriginalData.(fn2) = trimBuffer(Buffers.(fn2));
    end
    LoopTimestamps = loopTimeBuf(1:loopBufCount);

    %% ====================================================================
    %% IMMEDIATE STAGE 1 SAVE: EXPORT TO WORKSPACE AND DISK
    %% ====================================================================
    MocapSession = struct();
    MocapSession.OriginalData = OriginalData;
    
    % --> THIS KEEPS VARIABLES IN YOUR WORKSPACE AFTER STOPPING <--
    assignin('base', 'OriginalData', OriginalData);
    assignin('base', 'MocapSession', MocapSession);
    fprintf('\n[SUCCESS] STAGE 1: Raw data pushed directly to Base Workspace.\n');

    fileName = fullfile(outputFolder, ['MocapSession_' datestr(now, 'yyyymmdd_HHMMSS') '.mat']);
    try
        save(fileName, 'MocapSession');
        fprintf('[SUCCESS] STAGE 1: Raw data safely saved to MAT file.\n');
    catch ME
        warning('CRITICAL: Failed to save initial raw MAT file: %s', ME.message);
    end

    %% Initialize fallback analysis structures 
    robotName = '';
    Kinematics = struct();
    TrackingQuality = struct();
    RelativeMotion = struct();
    
    for idx = 1:numel(selectedNames)
        nm = matlab.lang.makeValidName(selectedNames{idx});
        nFramesCaptured = size(OriginalData.(nm).Position, 1);
        
        Kinematics.(nm).Velocity = NaN(nFramesCaptured, 3);
        Kinematics.(nm).Acceleration = NaN(nFramesCaptured, 3);
        Kinematics.(nm).AngularVelocity = NaN(nFramesCaptured, 3);
        
        TrackingQuality.(nm).GapCount = 0;
        TrackingQuality.(nm).MaxGapDuration = 0;
        TrackingQuality.(nm).IsTracked = false(nFramesCaptured, 1);
    end

    %% ====================================================================
    %% STAGE 2: POST-PROCESSING ANALYSIS (Wrapped Safely)
    %% ====================================================================
    fprintf('Running post-processing analysis...\n');
    try
        robotName = identifyRobotBody(fieldnames(OriginalData));
        if isempty(robotName)
            fprintf('[INFO] No Rigid Body with "robot" in its name was selected.\n');
        else
            fprintf('[INFO] Robot body identified as: %s\n', robotName);
        end

        Kinematics = computeKinematics(OriginalData);
        RelativeMotion = computeRelativeMotion(OriginalData, Kinematics, robotName, ...
            DANGER_THRESHOLD_MM, WARNING_THRESHOLD_MM, MIN_APPROACH_SPEED_MMPS);
        TrackingQuality = computeTrackingQuality(OriginalData);
        StaticBodies = detectStaticBodies(OriginalData, STATIC_POSITION_RANGE_MM, STATIC_EULER_RANGE_DEG);
        Latency = computeLatencyStats(LoopTimestamps);

        Metadata = struct();
        Metadata.Date = datestr(now);
        Metadata.TaskName = '';
        Metadata.RobotBodyName = robotName;
        Metadata.StaticBodies = StaticBodies;
        Metadata.SafetyThresholds = struct('DangerMM', DANGER_THRESHOLD_MM, ...
            'WarningMM', WARNING_THRESHOLD_MM, 'MinApproachSpeed_mmps', MIN_APPROACH_SPEED_MMPS);

        MocapSession.Analysis.Kinematics = Kinematics;
        MocapSession.Analysis.RelativeMotion = RelativeMotion;
        MocapSession.Analysis.TrackingQuality = TrackingQuality;
        MocapSession.Analysis.Latency = Latency;
        MocapSession.Analysis.Metadata = Metadata;
        MocapSession.Analysis.Figures = struct(); 
        
        % Update Workspace and File
        assignin('base', 'MocapSession', MocapSession);
        save(fileName, 'MocapSession');
        fprintf('[SUCCESS] STAGE 2: Analysis data updated in Workspace and MAT file.\n');
    catch ME
        warning('Analysis phase failed, but raw data is still safe! Error: %s', ME.message);
    end

    %% ====================================================================
    %% STAGE 3: FIGURES & DASHBOARD
    %% ====================================================================
    fprintf('Generating figures...\n');
    Figures = struct();
    try
        Figures = generateFigures(OriginalData, RelativeMotion, robotName, outputFolder);
    catch ME
        warning('Failed to generate individual figures: %s', ME.message);
    end

    fprintf('Generating dashboard (will open automatically)...\n');
    try
        dashboardPath = generateDashboard(OriginalData, Kinematics, RelativeMotion, ...
            TrackingQuality, robotName, outputFolder);
        Figures.Dashboard_path = dashboardPath;
    catch ME
        warning('Failed to generate dashboard: %s', ME.message);
    end

    %% Final Update of Workspace and MAT File
    try
        if isfield(MocapSession, 'Analysis')
            MocapSession.Analysis.Figures = Figures;
        else
            MocapSession.Analysis = struct('Figures', Figures);
        end
        assignin('base', 'MocapSession', MocapSession);
        save(fileName, 'MocapSession');
        fprintf('[SUCCESS] STAGE 3: Final details synchronized perfectly.\n');
    catch ME
        warning('Failed to update MAT file with figure paths: %s', ME.message);
    end

    fprintf('Session complete! Check your Workspace for "MocapSession". Output folder: %s\n', outputFolder);
end


%% ==================================================================
%  LOCAL (STATELESS) FUNCTIONS
%  ==================================================================

function natnetclient = connectToNatNet()
    fprintf('Creating natnet client object\n');
    natnetclient = natnet;
    natnetclient.HostIP = '127.0.0.1';
    natnetclient.ClientIP = '127.0.0.1';
    natnetclient.ConnectionType = 'Multicast';
    natnetclient.connect;
    if natnetclient.IsConnected == 0
        error(['Client failed to connect. Make sure Motive is running, ' ...
               'Broadcast Frame Data is enabled, and IP addresses are correct.']);
    end
    fprintf('Connected to Motive.\n');
end

function [idToName, rbNames] = buildRigidBodyMap(natnetclient)
    model = natnetclient.getModelDescription;
    if model.RigidBodyCount < 1
        error(['No Rigid Bodies found in Motive. Create at least one ' ...
               'Rigid Body asset and make sure it is visible before running this script.']);
    end
    idToName = containers.Map('KeyType', 'double', 'ValueType', 'char');
    rbNames = cell(1, model.RigidBodyCount);
    for i = 1:model.RigidBodyCount
        idToName(model.RigidBody(i).ID) = model.RigidBody(i).Name;
        rbNames{i} = model.RigidBody(i).Name;
    end
end

function selectedNames = selectRigidBodiesToRecord(rbNames)
    fprintf('\n--- Select which Rigid Bodies to record ---\n');
    fprintf('(Anything you answer "no" to will NOT be logged or plotted.)\n\n');
    selectedNames = {};
    for i = 1:numel(rbNames)
        prompt = sprintf('Record "%s"? (yes/no): ', rbNames{i});
        answer = input(prompt, 's');
        if ~isempty(answer) && strcmpi(answer(1), 'y')
            selectedNames{end+1} = rbNames{i}; %#ok<AGROW>
        end
    end
    fprintf('\nWill be recorded and plotted: ');
    if isempty(selectedNames)
        fprintf('(none)\n');
    else
        fprintf('%s\n', strjoin(selectedNames, ', '));
    end
    fprintf('--------------------------------------------\n\n');
end

function rbID = getRigidBodyID(rb)
    rbID = rb.ID;
end

function [rollDeg, pitchDeg, yawDeg] = quaternionToEuler(qx, qy, qz, qw)
    sinr_cosp = 2 * (qw*qx + qy*qz);
    cosr_cosp = 1 - 2 * (qx*qx + qy*qy);
    roll = atan2(sinr_cosp, cosr_cosp);
    sinp = 2 * (qw*qy - qz*qx);
    if abs(sinp) >= 1
        pitch = sign(sinp) * (pi/2);
    else
        pitch = asin(sinp);
    end
    siny_cosp = 2 * (qw*qz + qx*qy);
    cosy_cosp = 1 - 2 * (qy*qy + qz*qz);
    yaw = atan2(siny_cosp, cosy_cosp);
    rollDeg  = rad2deg(roll);
    pitchDeg = rad2deg(pitch);
    yawDeg   = rad2deg(yaw);
end

%% --- Buffer management ---
function buf = newBuffer(capacity)
    buf.Position   = NaN(capacity, 3);
    buf.Quaternion = NaN(capacity, 4);
    buf.Euler      = NaN(capacity, 3);
    buf.Time       = NaN(capacity, 1);
    buf.Count      = 0;
    buf.Capacity   = capacity;
end

function Buffers = initializeBuffers(names, capacity)
    Buffers = struct();
    for i = 1:numel(names)
        fn = matlab.lang.makeValidName(names{i});
        Buffers.(fn) = newBuffer(capacity);
    end
end

function buf = growBufferIfNeeded(buf)
    if buf.Count >= buf.Capacity
        newCap = buf.Capacity * 2;
        buf.Position(end+1:newCap, :)   = NaN;
        buf.Quaternion(end+1:newCap, :) = NaN;
        buf.Euler(end+1:newCap, :)      = NaN;
        buf.Time(end+1:newCap, 1)       = NaN;
        buf.Capacity = newCap;
    end
end

function buf = appendRow(buf, t, positionMM, quat, euler)
    buf = growBufferIfNeeded(buf);
    buf.Count = buf.Count + 1;
    buf.Position(buf.Count, :)   = positionMM;
    buf.Quaternion(buf.Count, :) = quat;
    buf.Euler(buf.Count, :)      = euler;
    buf.Time(buf.Count)          = t;
end

function buf = appendNaNRow(buf, t)
    buf = growBufferIfNeeded(buf);
    buf.Count = buf.Count + 1;
    buf.Position(buf.Count, :)   = NaN(1, 3);
    buf.Quaternion(buf.Count, :) = NaN(1, 4);
    buf.Euler(buf.Count, :)      = NaN(1, 3);
    buf.Time(buf.Count)          = t;
end

function out = trimBuffer(buf)
    n = buf.Count;
    out.Position   = buf.Position(1:n, :);
    out.Quaternion = buf.Quaternion(1:n, :);
    out.Euler      = buf.Euler(1:n, :);
    out.Time       = buf.Time(1:n);
end

%% --- Live plotting ---
function [figHandle, plotHandles, combinedHandles] = initializePlots(rbNames)
    numRB = numel(rbNames);
    figHandle = figure('Name', 'Multi-Rigid-Body Tracking', 'WindowStyle', 'docked');
    plotHandles = struct();
    combinedHandles = struct();

    if numRB == 0
        axis off;
        text(0.5, 0.5, 'No Rigid Bodies selected for plotting.', ...
             'HorizontalAlignment', 'center', 'FontSize', 12);
        return;
    end

    colors = lines(numRB);
    totalPanels = numRB + 1;

    for i = 1:numRB
        fieldName = matlab.lang.makeValidName(rbNames{i});
        displayName = strrep(rbNames{i}, '_', '\_');
        c = colors(i, :);

        subplot(1, totalPanels, i);
        title([displayName ' - 3D (live)']);
        xlabel('X (mm)'); ylabel('Y (mm)'); zlabel('Z (mm)');
        hold on; grid on; view(3); axis equal;
        
        hTraj = animatedline('Color', c, 'LineWidth', 1.2);
        plotHandles.(fieldName) = struct('Traj3D', hTraj);
    end

    subplot(1, totalPanels, totalPanels);
    title('Combined 3D (live)');
    xlabel('X (mm)'); ylabel('Y (mm)'); zlabel('Z (mm)');
    hold on; grid on; view(3); axis equal;
    for i = 1:numRB
        fieldName = matlab.lang.makeValidName(rbNames{i});
        displayName = strrep(rbNames{i}, '_', '\_');
        
        combinedHandles.(fieldName) = animatedline('Color', colors(i, :), ...
            'LineWidth', 1.2, 'DisplayName', displayName);
    end
    legend('show', 'Location', 'best');
end

%% --- Robot identification ---
function robotName = identifyRobotBody(fieldNamesList)
    robotName = '';
    matches = {};
    for i = 1:numel(fieldNamesList)
        if contains(lower(fieldNamesList{i}), 'robot')
            matches{end+1} = fieldNamesList{i}; %#ok<AGROW>
        end
    end
    if numel(matches) == 1
        robotName = matches{1};
    elseif numel(matches) > 1
        warning('Multiple Rigid Bodies matched "robot" (%s). Using the first: %s', ...
            strjoin(matches, ', '), matches{1});
        robotName = matches{1};
    end
end

%% --- Kinematics ---
function Kinematics = computeKinematics(OriginalData)
    Kinematics = struct();
    names = fieldnames(OriginalData);
    for i = 1:numel(names)
        fn = names{i};
        body = OriginalData.(fn);
        t = body.Time; pos = body.Position; eul = body.Euler;
        vel = NaN(size(pos)); acc = NaN(size(pos)); angVel = NaN(size(eul));
        if numel(t) >= 2
            dt = diff(t); dt(dt <= 0) = NaN;
            vel(2:end, :) = diff(pos, 1, 1) ./ dt;
            angVel(2:end, :) = diff(eul, 1, 1) ./ dt;
        end
        if numel(t) >= 3
            dt2 = diff(t(2:end)); dt2(dt2 <= 0) = NaN;
            acc(3:end, :) = diff(vel(2:end, :), 1, 1) ./ dt2;
        end
        Kinematics.(fn).Velocity = vel;
        Kinematics.(fn).Acceleration = acc;
        Kinematics.(fn).AngularVelocity = angVel;
    end
end

%% --- Relative motion / safety ---
function a = wrapAngle180(a)
    a = mod(a + 180, 360) - 180;
end

function RelativeMotion = computeRelativeMotion(OriginalData, Kinematics, robotName, dangerMM, warnMM, minApproachSpeed)
    RelativeMotion = struct();
    RelativeMotion.HumanNames = {};
    if isempty(robotName) || ~isfield(OriginalData, robotName)
        return;
    end
    robotPos = OriginalData.(robotName).Position;
    robotEuler = OriginalData.(robotName).Euler;
    robotVel = Kinematics.(robotName).Velocity;

    humanNames = setdiff(fieldnames(OriginalData), {robotName});
    nFrames = size(robotPos, 1);
    nHuman = numel(humanNames);

    distanceMatrix = NaN(nFrames, nHuman);
    robotApproachMatrix = false(nFrames, nHuman);
    humanApproachMatrix = false(nFrames, nHuman);

    for h = 1:nHuman
        hn = humanNames{h};
        humanPos = OriginalData.(hn).Position;
        humanVel = Kinematics.(hn).Velocity;
        if size(humanPos, 1) ~= nFrames
            continue
        end
        delta = humanPos - robotPos;
        dist = sqrt(sum(delta.^2, 2));
        distanceMatrix(:, h) = dist;
        dirUnit = delta ./ dist;

        worldBearing = atan2d(delta(:,2), delta(:,1));
        relativeBearing = wrapAngle180(worldBearing - robotEuler(:,3));

        robotTowardSpeed = sum(robotVel .* dirUnit, 2);
        humanTowardSpeed = sum(humanVel .* (-dirUnit), 2);
        robotApproachMatrix(:, h) = robotTowardSpeed > minApproachSpeed;
        humanApproachMatrix(:, h) = humanTowardSpeed > minApproachSpeed;

        RelativeMotion.(hn).Distance = dist;
        RelativeMotion.(hn).Direction = relativeBearing;
    end

    [minDist, minIdx] = min(distanceMatrix, [], 2);
    SafetyLevel = zeros(nFrames, 1);
    SafetyLevel(minDist <= warnMM) = 1;
    SafetyLevel(minDist <= dangerMM) = 2;
    SafetyLevel(isnan(minDist)) = NaN;

    minDistSourceName = repmat({''}, nFrames, 1);
    for f = 1:nFrames
        if ~isnan(minIdx(f)) && minIdx(f) >= 1 && minIdx(f) <= nHuman
            minDistSourceName{f} = humanNames{minIdx(f)};
        end
    end

    RelativeMotion.MinDistance = minDist;
    RelativeMotion.MinDistanceSource = minDistSourceName;
    RelativeMotion.SafetyLevel = SafetyLevel;
    RelativeMotion.RobotApproaching = robotApproachMatrix;
    RelativeMotion.HumanApproaching = humanApproachMatrix;
    RelativeMotion.HumanNames = humanNames;
    RelativeMotion.Thresholds = struct('DangerMM', dangerMM, 'WarningMM', warnMM, ...
        'MinApproachSpeed_mmps', minApproachSpeed);
end

%% --- Tracking quality ---
function runs = findGapRuns(isTracked, t)
    runs = {};
    n = numel(isTracked);
    i = 1;
    while i <= n
        if ~isTracked(i)
            j = i;
            while j <= n && ~isTracked(j)
                j = j + 1;
            end
            lastIdx = min(j, n);
            runs{end+1} = struct('startIdx', i, 'endIdx', j-1, 'duration', t(lastIdx) - t(i)); %#ok<AGROW>
            i = j;
        else
            i = i + 1;
        end
    end
end

function TrackingQuality = computeTrackingQuality(OriginalData)
    TrackingQuality = struct();
    names = fieldnames(OriginalData);
    for i = 1:numel(names)
        fn = names{i};
        body = OriginalData.(fn);
        isTracked = ~any(isnan(body.Position), 2);
        gapRuns = findGapRuns(isTracked, body.Time);
        TrackingQuality.(fn).IsTracked = isTracked;
        TrackingQuality.(fn).GapCount = numel(gapRuns);
        if isempty(gapRuns)
            TrackingQuality.(fn).MaxGapDuration = 0;
        else
            TrackingQuality.(fn).MaxGapDuration = max(cellfun(@(g) g.duration, gapRuns));
        end
    end
end

%% --- Static body detection ---
function StaticBodies = detectStaticBodies(OriginalData, posRangeMM, eulerRangeDeg)
    StaticBodies = struct();
    names = fieldnames(OriginalData);
    for i = 1:numel(names)
        fn = names{i};
        body = OriginalData.(fn);
        validRows = ~any(isnan(body.Position), 2);
        if ~any(validRows)
            StaticBodies.(fn).Classification = 'NeverTracked';
            StaticBodies.(fn).Note = 'Never successfully tracked';
            StaticBodies.(fn).ReferencePosition = NaN(1, 3);
            StaticBodies.(fn).ReferenceQuaternion = NaN(1, 4);
            continue;
        end
        posRange = max(body.Position(validRows, :), [], 1) - min(body.Position(validRows, :), [], 1);
        eulRange = max(body.Euler(validRows, :), [], 1) - min(body.Euler(validRows, :), [], 1);
        if all(posRange <= posRangeMM) && all(eulRange <= eulerRangeDeg)
            StaticBodies.(fn).Classification = 'Static';
            StaticBodies.(fn).Note = 'Static/reference object';
            firstValid = find(validRows, 1);
            StaticBodies.(fn).ReferencePosition = body.Position(firstValid, :);
            StaticBodies.(fn).ReferenceQuaternion = body.Quaternion(firstValid, :);
        end
    end
end

%% --- Latency ---
function Latency = computeLatencyStats(loopTimestamps)
    Latency = struct();
    if numel(loopTimestamps) < 2
        Latency.InterFrameDt = []; Latency.MeanDt = NaN; Latency.MaxDt = NaN; Latency.StdDt = NaN;
        return;
    end
    dt = diff(loopTimestamps);
    Latency.InterFrameDt = dt;
    Latency.MeanDt = mean(dt);
    Latency.MaxDt = max(dt);
    Latency.StdDt = std(dt);
end

%% --- Figures ---
function Figures = generateFigures(OriginalData, RelativeMotion, robotName, outputFolder)
    Figures = struct();
    names = fieldnames(OriginalData);
    colors = lines(numel(names));

    for i = 1:numel(names)
        fn = names{i};
        body = OriginalData.(fn);
        c = colors(i, :);
        displayName = strrep(fn, '_', '\_');

        f1 = figure('Visible', 'off');
        plot(body.Time, body.Position(:,1), 'r', body.Time, body.Position(:,2), 'g', body.Time, body.Position(:,3), 'b');
        legend('X', 'Y', 'Z', 'Location', 'best');
        xlabel('Time (s)'); ylabel('Position (mm)'); title([displayName ' - Position']); grid on;
        p1 = fullfile(outputFolder, [fn '_Position']);
        try savefig(f1, [p1 '.fig']); catch, end
        try saveas(f1, [p1 '.png']); catch, end
        close(f1);
        Figures.(fn).PositionPlot_path = [p1 '.png'];

        f2 = figure('Visible', 'off');
        plot(body.Time, body.Euler(:,1), 'r', body.Time, body.Euler(:,2), 'g', body.Time, body.Euler(:,3), 'b');
        legend('Roll', 'Pitch', 'Yaw', 'Location', 'best');
        xlabel('Time (s)'); ylabel('Angle (deg)'); title([displayName ' - Orientation']); grid on;
        p2 = fullfile(outputFolder, [fn '_Orientation']);
        try savefig(f2, [p2 '.fig']); catch, end
        try saveas(f2, [p2 '.png']); catch, end
        close(f2);
        Figures.(fn).OrientationPlot_path = [p2 '.png'];

        f3 = figure('Visible', 'off');
        validRows = ~any(isnan(body.Position), 2);
        plot3(body.Position(validRows,1), body.Position(validRows,2), body.Position(validRows,3), 'Color', c);
        hold on;
        idxValid = find(validRows);
        if ~isempty(idxValid)
            plot3(body.Position(idxValid(1),1), body.Position(idxValid(1),2), body.Position(idxValid(1),3), ...
                'go', 'MarkerSize', 10, 'MarkerFaceColor', 'g');
            plot3(body.Position(idxValid(end),1), body.Position(idxValid(end),2), body.Position(idxValid(end),3), ...
                'rx', 'MarkerSize', 10, 'LineWidth', 2);
        end
        xlabel('X (mm)'); ylabel('Y (mm)'); zlabel('Z (mm)');
        legend({displayName, 'Start', 'End'}, 'Location', 'best');
        title([displayName ' - 3D Trajectory']); grid on; axis equal; view(3);
        p3 = fullfile(outputFolder, [fn '_Trajectory3D']);
        try savefig(f3, [p3 '.fig']); catch, end
        try saveas(f3, [p3 '.png']); catch, end
        close(f3);
        Figures.(fn).Trajectory3D_path = [p3 '.png'];
    end
end

%% --- Dashboard ---
function dashboardPath = generateDashboard(OriginalData, Kinematics, RelativeMotion, TrackingQuality, robotName, outputFolder)
    names = fieldnames(OriginalData);
    n = numel(names);
    colors = lines(n);
    hasRobotAnalysis = ~isempty(robotName) && isfield(RelativeMotion, 'SafetyLevel') && isfield(OriginalData, robotName);

    fDash = figure('Name', 'Mocap Session Dashboard', 'Position', [50 50 1600 1000]);
    tl = tiledlayout(fDash, 'flow', 'TileSpacing', 'compact', 'Padding', 'compact');
    title(tl, 'Mocap Session Dashboard');

    for i = 1:n
        fn = names{i};
        body = OriginalData.(fn);
        c = colors(i, :);
        displayName = strrep(fn, '_', '\_');

        nexttile(tl);
        plot(body.Time, body.Position); legend('X', 'Y', 'Z', 'Location', 'best');
        xlabel('Time (s)'); ylabel('mm'); title([displayName ' Position']); grid on;
    end

    nexttile(tl);
    hold on;
    for i = 1:n
        fn = names{i};
        body = OriginalData.(fn);
        c = colors(i, :);
        validRows = ~any(isnan(body.Position), 2);
        pos = body.Position(validRows, :);
        if size(pos, 1) > 3000
            idxSub = round(linspace(1, size(pos,1), 3000));
            pos = pos(idxSub, :);
        end
        plot3(pos(:,1), pos(:,2), pos(:,3), 'Color', c, 'LineWidth', 1.2);
    end
    xlabel('X'); ylabel('Y'); zlabel('Z'); title('Combined 3D (all bodies)'); grid on; axis equal; view(3);
    legend(strrep(names, '_', '\_'), 'Location', 'best');

    dashboardBasePath = fullfile(outputFolder, 'Dashboard');
    try savefig(fDash, [dashboardBasePath '.fig']); catch, end
    try saveas(fDash, [dashboardBasePath '.png']); catch, end
    dashboardPath = [dashboardBasePath '.png'];
end