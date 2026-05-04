port { prisma } from ''../utils/prisma'';
import { awardXp, XP_REWARDS } from ''./xpService'';

export interface WorkoutParams {
  durationMins: number;
  intensity: ''recovery'' | ''easy'' | ''moderate'' | ''hard'';
  goal: string;
  equipment: string[];
  energyState: ''green'' | ''yellow'' | ''red'';
  position?: string;
}

function getXpForWorkout(intensity: string): number {
  const map: Record<string, number> = {
    recovery: 30,
    easy: XP_REWARDS.workout_easy,
    moderate: XP_REWARDS.workout_moderate,
    hard: XP_REWARDS.workout_hard,
  };
  return map[intensity] || 50;
}

function generateExercises(params: WorkoutParams) {
  const { intensity, goal, equipment, energyState, durationMins } = params;
  const hasFootball = equipment.some((e) => [''football'', ''cones'', ''agility_ladder''].includes(e));
  const hasGym = equipment.some((e) => [''dumbbells'', ''barbell'', ''full_gym_access'', ''squat_rack''].includes(e));
  const hasTreadmill = equipment.some((e) => [''treadmill'', ''walking_pad''].includes(e));
  const hasBike = equipment.includes(''exercise_bike'');
  const hasRower = equipment.includes(''rowing_machine'');
  const hasKettlebell = equipment.includes(''kettlebells'');

  // Red day override - recovery only
  if (energyState === ''red'') {
    return {
      title: ''Recovery & Mobility Session'',
      warmup: [
        { name: ''Gentle walking'', duration: ''5 mins'', notes: ''Very easy pace'' },
        { name: ''Deep breathing'', duration: ''2 mins'', sets: '''', reps: '''' },
      ],
      main: [
        { name: ''Lying knee hugs'', sets: ''2'', reps: ''10 each'', rest: ''30s'' },
        { name: ''Cat-cow stretch'', sets: ''2'', duration: ''60s'', rest: ''20s'' },
        { name: ''Hip circles'', sets: ''2'', reps: ''10 each side'', rest: ''20s'' },
        { name: ''Seated forward fold'', sets: ''2'', duration: ''60s'', rest: ''30s'' },
        { name: ''Box breathing'', sets: ''3'', duration: ''60s'', rest: ''10s'' },
        { name: ''Gentle walking'', duration: ''5 mins'', notes: ''Cool down'' },
      ],
      cooldown: [{ name: ''Full body stretch'', duration: ''5 mins'' }],
      statsImproved: [''recovery''],
      xpReward: 30,
      estimatedFatigue: 1,
    };
  }

  const warmup = [
    { name: ''Light jog / march on spot'', duration: ''3 mins'' },
    { name: ''Leg swings'', sets: ''2'', reps: ''10 each side'' },
    { name: ''Arm circles'', sets: ''2'', reps: ''10 each direction'' },
    { name: ''Hip openers'', sets: ''2'', reps: ''8 each side'' },
  ];

  const cooldown = [
    { name: ''Walking cool-down'', duration: ''3 mins'' },
    { name: ''Hamstring stretch'', duration: ''60s each leg'' },
    { name: ''Quad stretch'', duration: ''45s each leg'' },
    { name: ''Hip flexor stretch'', duration: ''60s each side'' },
  ];

  let main: object[] = [];
  let statsImproved: string[] = [];

  if (goal === ''stamina'') {
    statsImproved = [''stamina'', ''recovery''];
    if (hasRower) {
      main = [
        { name: ''Rowing machine'', sets: ''1'', duration: `${Math.floor(durationMins * 0.7)} mins`, intensity: intensity === ''hard'' ? ''80-90% effort'' : ''65-75% effort'', rest: ''2 mins'' },
        { name: ''Step-ups'', sets: ''3'', reps: ''15 each leg'', rest: ''45s'' },
      ];
    } else if (hasTreadmill) {
      main = [
        { name: ''Treadmill intervals'', sets: ''6'', duration: ''2 mins on / 1 min walk'', notes: intensity === ''hard'' ? ''8-9 RPE'' : ''6-7 RPE'' },
        { name: ''Bodyweight squats'', sets: ''3'', reps: ''20'', rest: ''30s'' },
      ];
    } else {
      main = [
        { name: ''Burpees'', sets: ''4'', reps: intensity === ''hard'' ? ''15'' : ''10'', rest: ''60s'' },
        { name: ''Mountain climbers'', sets: ''3'', duration: ''45s'', rest: ''30s'' },
        { name: ''Jump squats'', sets: ''3'', reps: ''12'', rest: ''45s'' },
        { name: ''High knees'', sets: ''3'', duration: ''30s'', rest: ''30s'' },
      ];
    }
  } else if (goal === ''strength'') {
    statsImproved = [''physical'', ''defending''];
    if (hasGym) {
      main = [
        { name: ''Barbell squat'', sets: ''4'', reps: intensity === ''hard'' ? ''6'' : ''10'', rest: ''90s'' },
        { name: ''Romanian deadlift'', sets: ''3'', reps: ''8'', rest: ''90s'' },
        { name: ''Bench press'', sets: ''4'', reps: ''8'', rest: ''90s'' },
        { name: ''Dumbbell rows'', sets: ''3'', reps: ''10 each'', rest: ''60s'' },
        { name: ''Plank'', sets: ''3'', duration: ''60s'', rest: ''45s'' },
      ];
    } else if (hasKettlebell) {
      main = [
        { name: ''Kettlebell swings'', sets: ''4'', reps: ''15'', rest: ''60s'' },
        { name: ''Goblet squat'', sets: ''3'', reps: ''12'', rest: ''60s'' },
        { name: ''Single-arm KB row'', sets: ''3'', reps: ''10 each'', rest: ''45s'' },
        { name: ''KB Romanian deadlift'', sets: ''3'', reps: ''10'', rest: ''60s'' },
      ];
    } else {
      main = [
        { name: ''Push-ups'', sets: ''4'', reps: intensity === ''hard'' ? ''20'' : ''12'', rest: ''60s'' },
        { name: ''Bulgarian split squats'', sets: ''3'', reps: ''10 each'', rest: ''60s'' },
        { name: ''Pike push-ups'', sets: ''3'', reps: ''10'', rest: ''45s'' },
        { name: ''Glute bridges'', sets: ''3'', reps: ''15'', rest: ''30s'' },
        { name: ''Plank'', sets: ''3'', duration: ''60s'', rest: ''30s'' },
      ];
    }
  } else if (goal === ''speed'' || goal === ''agility'') {
    statsImproved = [''pace'', ''dribbling''];
    if (hasFootball) {
      main = [
        { name: ''5-10-5 shuttle drill'', sets: ''6'', rest: ''90s'', notes: ''Max effort'' },
        { name: ''Cone dribbling slalom'', sets: ''5'', rest: ''60s'', notes: ''Quick feet'' },
        { name: ''Agility ladder - two feet each box'', sets: ''4'', duration: ''30s'', rest: ''60s'' },
        { name: ''Acceleration runs 20m'', sets: ''6'', rest: ''90s'' },
      ];
    } else {
      main = [
        { name: ''10m acceleration sprints'', sets: ''8'', rest: ''90s'' },
        { name: ''Lateral shuffles'', sets: ''4'', duration: ''20s'', rest: ''40s'' },
        { name: ''T-drill (cones or markers)'', sets: ''5'', rest: ''90s'' },
        { name: ''Broad jumps'', sets: ''3'', reps: ''6'', rest: ''60s'' },
      ];
    }
  } else if (goal === ''football_skill'') {
    statsImproved = [''passing'', ''shooting'', ''dribbling''];
    main = [
      { name: ''Ball mastery - sole rolls'', sets: ''3'', duration: ''60s'' },
      { name: ''Wall passing (if available)'', sets: ''5'', duration: ''2 mins'', notes: ''Focus on first touch'' },
      { name: ''Shooting practice'', sets: ''3'', reps: ''10 shots'', notes: ''Vary placement'' },
      { name: ''Dribbling course (cones)'', sets: ''5'', rest: ''45s'' },
      { name: ''Keep-ups'', sets: ''3'', duration: ''2 mins'' },
    ];
  } else if (goal === ''mobility'' || goal === ''recovery'') {
    statsImproved = [''recovery'', ''composure''];
    main = [
      { name: ''World greatest stretch'', sets: ''2'', reps: ''8 each side'', rest: ''20s'' },
      { name: ''Pigeon pose'', sets: ''2'', duration: ''90s each side'', rest: ''20s'' },
      { name: ''Thoracic rotation'', sets: ''2'', reps: ''10 each side'' },
      { name: ''Hip 90/90 stretch'', sets: ''2'', duration: ''60s each'', rest: ''20s'' },
      { name: ''Shoulder cross-body stretch'', sets: ''2'', duration: ''45s each'' },
      { name: ''Box breathing'', sets: ''3'', duration: ''2 mins'', rest: ''30s'' },
    ];
  } else if (goal === ''match_simulation'') {
    statsImproved = [''stamina'', ''pace'', ''composure''];
    main = [
      { name: ''Warm-up rondos'', sets: ''2'', duration: ''5 mins'' },
      { name: ''High intensity intervals (match simulation)'', sets: ''6'', duration: ''4 mins on / 2 min walk'', notes: ''90% effort during work'' },
      { name: ''Sprint + recover shuttles'', sets: ''4'', rest: ''60s'' },
      { name: ''Core stability'', sets: ''3'', duration: ''45s'', rest: ''30s'' },
    ];
  } else {
    statsImproved = [''stamina'', ''physical''];
    main = [
      { name: ''Bodyweight squats'', sets: ''3'', reps: ''15'', rest: ''45s'' },
      { name: ''Push-ups'', sets: ''3'', reps: ''12'', rest: ''45s'' },
      { name: ''Lunges'', sets: ''3'', reps: ''10 each'', rest: ''45s'' },
      { name: ''Plank'', sets: ''3'', duration: ''45s'', rest: ''30s'' },
      { name: ''Jumping jacks'', sets: ''3'', duration: ''30s'', rest: ''30s'' },
    ];
  }

  return {
    title: `${intensity.charAt(0).toUpperCase() + intensity.slice(1)} ${goal.replace(/_/g, '' '')} Session`,
    warmup,
    main,
    cooldown,
    statsImproved,
    xpReward: getXpForWorkout(intensity),
    estimatedFatigue: intensity === ''hard'' ? 4 : intensity === ''moderate'' ? 3 : intensity === ''easy'' ? 2 : 1,
  };
}

export async function generateWorkout(userId: string, params: WorkoutParams) {
  const generated = generateExercises(params);
  const workout = await prisma.generatedWorkout.create({
    data: {
      userId,
      title: generated.title,
      category: params.goal,
      difficulty: params.intensity,
      durationMins: params.durationMins,
      energyState: params.energyState,
      xpReward: generated.xpReward,
      estimatedFatigue: generated.estimatedFatigue,
      warmup: generated.warmup,
      mainSection: generated.main,
      cooldown: generated.cooldown,
      statsImproved: generated.statsImproved,
    },
  });
  return workout;
}

export async function completeWorkout(userId: string, generatedWorkoutId: string, rpe: number, notes?: string) {
  const gw = await prisma.generatedWorkout.findUnique({ where: { id: generatedWorkoutId } });
  if (!gw || gw.userId !== userId) throw new Error(''Workout not found'');

  const workout = await prisma.$transaction(async (tx) => {
    const w = await tx.workout.create({
      data: {
        userId,
        generatedWorkoutId,
        title: gw.title,
        category: gw.category,
        difficulty: gw.difficulty,
        durationMins: gw.durationMins,
        rpe,
        notes,
        xpAwarded: gw.xpReward,
        statsImproved: gw.statsImproved,
        equipmentUsed: [],
      },
    });
    await tx.generatedWorkout.update({ where: { id: generatedWorkoutId }, data: { isCompleted: true, completedAt: new Date() } });
    return w;
  });

  await awardXp(userId, gw.xpReward, ''workout'', `Completed: ${gw.title}`);
  return workout;
}
