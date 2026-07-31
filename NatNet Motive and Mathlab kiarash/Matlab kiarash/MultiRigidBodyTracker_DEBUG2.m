function MultiRigidBodyTracker_DEBUG()
% MULTIRIGIDBODYTRACKER_DEBUG
%
% Diagnostic copy of MultiRigidBodyTracker.m. Architecture, plotting,
% ID-based lookup, data structure, and user interface are UNCHANGED.
% The only additions are diagnostic fprintf/disp statements to answer
% three specific questions before we touch any real logic:
%
%   1. Does frame.RigidBodies really contain every selected Rigid Body,
%      every frame -- or only one?
%   2. Do model.RigidBody(i).ID and frame.RigidBodies(k).ID share the
%      same numeric class (both double, or is one single/int32/etc,
%      which would silently break the containers.Map ID lookup)?
%   3. Does the frame data carry any tracking-validity field (Tracked,
%      TrackingValid, Params, etc.) that the current code ignores?
%
% HOW TO USE
%   Run this instead of MultiRigidBodyTracker.m for a short test (10-20
%   seconds is enough with 2-3 Rigid Bodies visible). Watch the Command
%   Window output, then send/paste it back for analysis. Close the
%   figure to stop, exactly like the normal version.

    fprintf('Multi-Rigid-Body NatNet Tracker [DEBUG MODE] - Start\n');
    fprintf('=========================================================\n');

    %% 1. NatNet initialization (unchanged)
    natnetclient = connectToNatNet();

    %% 2. Rigid Body identification (unchanged)
    [idToName, rbNames] = buildRigidBodyMap(natnetclient);
    numRB = numel(rbNames);
    fprintf('Detected %d Rigid Body/Bodies from Motive:\n', numRB);
    for i = 1:numRB
        fprintf('   - %s\n', rbNames{i});
    end

    % --- DEBUG: check the numeric class of IDs in the model description ---
    fprintf('\n[DEBUG] Model description ID classes:\n');
    model = natnetclient.getModelDescription; % extra call, read-only, harmless
    for i = 1:model.RigidBodyCount
        fprintf('   - %-20s ID=%s (class: %s)\n', model.RigidBody(i).Name, ...
                num2str(model.RigidBody(i).ID), class(model.RigidBody(i).ID));
    end
    fprintf('\n');

    %% 3. Selection (unchanged)
    selectedNames = selectRigidBodiesToRecord(rbNames);

    %% 4. Data storage (unchanged)
    Data = initializeDataStorage(selectedNames);

    %% 5. Plots (unchanged)
    [figHandle, plotHandles] = initializePlots(selectedNames);

    %% 6. Receive Frame loop -- WITH DEBUG PRINTS ADDED
    fprintf('\n[DEBUG] Streaming started. Watch the Command Window.\n');
    fprintf('[DEBUG] Close the figure window to stop.\n\n');
    startTime = tic;
    firstFrameChecked = false;

    while ishandle(figHandle)
        frame = natnetclient.getFrame;

        if isempty(frame)
            pause(0.001);
            continue;
        end

        % isfield() does not reliably work on the raw .NET frame object,
        % so probe nRigidBodies with try/catch instead.
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

        % --- DEBUG: direct comparison, this is the whole point of this file ---
        fprintf('[DEBUG] Frame %d | t=%.2fs | numel(frame.RigidBodies)=%d  vs  frame.nRigidBodies=%d\n', ...
                frame.iFrame, t, numel(frame.RigidBodies), frame.nRigidBodies);

        for k = 1:numRBInFrame
            try
                dbgRB = frame.RigidBodies(k);
            catch indexErr
                fprintf('   [%d] INDEX ERROR: %s\n', k, indexErr.message);
                continue
            end
            dbgID = getRigidBodyID(dbgRB);
            if isKey(idToName, dbgID)
                dbgName = idToName(dbgID);
            else
                dbgName = 'UNKNOWN (not in idToName map)';
            end
            fprintf('   [%d] ID=%-6s (class %-8s) -> %s\n', ...
                    k, num2str(dbgID), class(dbgID), dbgName);
        end

        % --- DEBUG: one-time deep inspection of the first frame only ---
        if ~firstFrameChecked
            fprintf('\n[DEBUG] --- One-time inspection of frame.RigidBodies(1) ---\n');
            fprintf('[DEBUG] Available fields on a RigidBody frame entry:\n');
            disp(fieldnames(frame.RigidBodies(1)));
            fprintf('[DEBUG] Full contents of frame.RigidBodies(1):\n');
            disp(frame.RigidBodies(1));
            if numel(frame.RigidBodies) >= 1 && model.RigidBodyCount >= 1
                fprintf('[DEBUG] ID class comparison: model=%s vs frame=%s\n', ...
                        class(model.RigidBody(1).ID), class(dbgID));
            end
            fprintf('[DEBUG] --- End one-time inspection ---\n\n');
            firstFrameChecked = true;
        end

        % --- Normal processing below: same fix applied as the working version ---
        for k = 1:numRBInFrame
            try
                rb = frame.RigidBodies(k);
            catch
                continue
            end
            rbID = getRigidBodyID(rb);

            if ~isKey(idToName, rbID)
                [idToName, ~] = buildRigidBodyMap(natnetclient);
                continue
            end

            name = idToName(rbID);
            fieldName = matlab.lang.makeValidName(name);

            if ~isfield(Data, fieldName)
                continue
            end

            [roll, pitch, yaw] = quaternionToEuler(double(rb.qx), double(rb.qy), double(rb.qz), double(rb.qw));
            positionMM = double([rb.x, rb.y, rb.z]) * 1000;

            Data.(fieldName).Time(end+1)                    = t;
            Data.(fieldName).Position(end+1, :)             = positionMM;
            Data.(fieldName).Orientation.Quaternion(end+1,:) = double([rb.qx, rb.qy, rb.qz, rb.qw]);
            Data.(fieldName).Orientation.Euler(end+1, :)     = [roll, pitch, yaw];

            if isfield(plotHandles, fieldName)
                updatePlots(plotHandles.(fieldName), t, positionMM, [roll, pitch, yaw]);
            end
        end

        drawnow limitrate;
    end

    %% 7. Cleanup and save (unchanged)
    fprintf('=========================================================\n');
    fprintf('Figure closed - disconnecting and saving DEBUG session data.\n');
    natnetclient.disconnect;

    fileName = ['MocapSession_DEBUG_' datestr(now, 'yyyymmdd_HHMMSS') '.mat'];
    save(fileName, 'Data');
    fprintf('Saved: %s\n', fileName);
    fprintf('Multi-Rigid-Body NatNet Tracker [DEBUG MODE] - End\n');
end


%% ------------------------------------------------------------------
%  LOCAL FUNCTIONS (identical to the working version -- unchanged)
%  ------------------------------------------------------------------

function natnetclient = connectToNatNet()
    fprintf('Creating natnet client object\n');
    natnetclient = natnet;

    natnetclient.HostIP = '127.0.0.1';
    natnetclient.ClientIP = '127.0.0.1';
    natnetclient.ConnectionType = 'Multicast';
    natnetclient.connect;

    if natnetclient.IsConnected == 0
        error(['Client failed to connect. Make sure Motive is running, ' ...
               'Broadcast Frame Data is enabled in the Data Streaming ' ...
               'pane, and the Host/Client IP addresses are correct.']);
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
        rbID   = model.RigidBody(i).ID;
        rbName = model.RigidBody(i).Name;
        idToName(rbID) = rbName;
        rbNames{i} = rbName;
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


function Data = initializeDataStorage(rbNames)
    Data = struct();
    for i = 1:numel(rbNames)
        fieldName = matlab.lang.makeValidName(rbNames{i});
        Data.(fieldName) = newRigidBodyRecord();
    end
end


function record = newRigidBodyRecord()
    record.Time = [];
    record.Position = zeros(0, 3);
    record.Orientation.Quaternion = zeros(0, 4);
    record.Orientation.Euler = zeros(0, 3);
end


function [figHandle, plotHandles] = initializePlots(rbNames)
    numRB = numel(rbNames);

    figHandle = figure('Name', 'Multi-Rigid-Body Tracking [DEBUG]', ...
                        'WindowStyle', 'docked');

    plotHandles = struct();

    if numRB == 0
        axis off;
        text(0.5, 0.5, 'No Rigid Bodies selected for plotting.', ...
             'HorizontalAlignment', 'center', 'FontSize', 12);
        text(0.5, 0.4, 'Data is still being logged. Close this window to stop.', ...
             'HorizontalAlignment', 'center', 'FontSize', 10, 'Color', [0.4 0.4 0.4]);
        return;
    end

    for i = 1:numRB
        fieldName = matlab.lang.makeValidName(rbNames{i});
        displayName = strrep(rbNames{i}, '_', '\_');

        subplot(numRB, 2, 2*i - 1);
        title([displayName ' - Position']);
        xlabel('Time (s)'); ylabel('Position (mm)');
        hold on; grid on;
        hX = animatedline('Color', [1 0 0], 'DisplayName', 'X');
        hY = animatedline('Color', [0 1 0], 'DisplayName', 'Y');
        hZ = animatedline('Color', [0 0 1], 'DisplayName', 'Z');
        legend('show', 'Location', 'best');

        subplot(numRB, 2, 2*i);
        title([displayName ' - Orientation']);
        xlabel('Time (s)'); ylabel('Angle (deg)');
        hold on; grid on;
        hRoll  = animatedline('Color', [1 0 0], 'DisplayName', 'Roll');
        hPitch = animatedline('Color', [0 1 0], 'DisplayName', 'Pitch');
        hYaw   = animatedline('Color', [0 0 1], 'DisplayName', 'Yaw');
        legend('show', 'Location', 'best');

        plotHandles.(fieldName) = struct( ...
            'X', hX, 'Y', hY, 'Z', hZ, ...
            'Roll', hRoll, 'Pitch', hPitch, 'Yaw', hYaw);
    end
end


function updatePlots(h, t, positionMM, eulerDeg)
    addpoints(h.X, t, positionMM(1));
    addpoints(h.Y, t, positionMM(2));
    addpoints(h.Z, t, positionMM(3));

    addpoints(h.Roll,  t, eulerDeg(1));
    addpoints(h.Pitch, t, eulerDeg(2));
    addpoints(h.Yaw,   t, eulerDeg(3));
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
