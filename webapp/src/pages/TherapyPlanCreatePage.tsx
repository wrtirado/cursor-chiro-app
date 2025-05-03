// src/pages/TherapyPlanCreatePage.tsx
import React, { useState, FormEvent } from "react";
import {
  Container,
  Typography,
  Box,
  TextField,
  Button,
  CircularProgress,
  Alert,
  Paper,
  Divider,
  IconButton,
  Grid,
} from "@mui/material";
import AddIcon from "@mui/icons-material/Add";
import DeleteIcon from "@mui/icons-material/Delete";
import apiClient from "../lib/axios";
import { useNavigate } from "react-router-dom";

// Interface matching the backend PlanExerciseCreate schema
interface ExerciseInput {
  title: string;
  instructions: string; // Use empty string for optional fields initially
  sequence_order: number;
  // image_url and video_url will be handled separately
}

// Interface matching the backend TherapyPlanCreate schema
interface TherapyPlanInput {
  title: string;
  description: string; // Use empty string for optional fields initially
  exercises: ExerciseInput[];
}


function TherapyPlanCreatePage() {
  const navigate = useNavigate();
  const [plan, setPlan] = useState<TherapyPlanInput>({
    title: "",
    description: "",
    exercises: [],
  });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // --- Plan Title/Description Handler ---
  const handlePlanChange = (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
    const { name, value } = event.target;
    setPlan((prevPlan: TherapyPlanInput) => ({
      ...prevPlan,
      [name]: value,
    }));
  };

  // --- Exercise Management Handlers ---
  const addExercise = () => {
    setPlan((prevPlan: TherapyPlanInput) => ({
      ...prevPlan,
      exercises: [
        ...prevPlan.exercises,
        {
          title: "", // Start with empty fields
          instructions: "",
          // Assign sequence order based on the new length + 1
          sequence_order: prevPlan.exercises.length + 1,
        },
      ],
    }));
  };

  const handleExerciseChange = (index: number, field: keyof Omit<ExerciseInput, 'sequence_order'>, value: string) => {
      // We only handle string fields here (title, instructions). Sequence order is managed automatically.
    setPlan((prevPlan: TherapyPlanInput) => {
      const updatedExercises = [...prevPlan.exercises];
      // Ensure the exercise exists at the index before trying to update
      if (updatedExercises[index]) {
        updatedExercises[index] = {
          ...updatedExercises[index],
          [field]: value,
        };
      }
      return { ...prevPlan, exercises: updatedExercises };
    });
  };

  const removeExercise = (index: number) => {
    setPlan((prevPlan: TherapyPlanInput) => {
        // Create a new array excluding the item at the specified index
      const filteredExercises = prevPlan.exercises.filter((_, i) => i !== index);
        // Re-calculate sequence_order for the remaining exercises
      const updatedExercises = filteredExercises.map((exercise, i) => ({
          ...exercise,
          sequence_order: i + 1,
      }));
      return { ...prevPlan, exercises: updatedExercises };
    });
  };

  // --- Form Submission Handler ---
  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(null);
    // console.log("Submitting Plan:", plan); // Keep for debugging if needed

    // Validate exercises: ensure titles are present and sequence_order is valid
    if (plan.exercises.some((ex: ExerciseInput) => !ex.title.trim())) {
        setError("All exercises must have a title.");
        setLoading(false);
        return;
    }
    if (plan.exercises.some((ex: ExerciseInput) => ex.sequence_order <= 0)) {
        setError("Internal error: Invalid exercise sequence order detected.");
        setLoading(false);
        return;
    }

    try {
      // Send the plan state, which matches TherapyPlanCreate schema
      const response = await apiClient.post("/plans", plan);

      if (response.status === 201) { // Check for 201 Created status
        setSuccess("Therapy plan created successfully!");
        // Reset form after successful creation
        setPlan({ title: "", description: "", exercises: [] });
        // Optional: Navigate to a different page, e.g., plans list or the new plan detail
        // navigate('/plans');
      } else {
         // Handle unexpected success statuses if necessary
        throw new Error(response.data?.detail || `Failed to create plan with status: ${response.status}`);
      }
    } catch (err: any) {
      console.error("Plan creation error:", err);
      setError(err.response?.data?.detail || err.message || "Failed to create plan.");
    } finally {
      setLoading(false);
    }

    // Remove simulation code
    // await new Promise(resolve => setTimeout(resolve, 1000));
    // setLoading(false);
    // setError("API call not implemented yet.");
    // setSuccess("Plan submission simulated.");
  };


  return (
    <Container maxWidth="md" sx={{ mt: 4, mb: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Create New Therapy Plan
      </Typography>

      <Paper sx={{ p: 3 }}>
        <Box component="form" onSubmit={handleSubmit} noValidate>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          {success && <Alert severity="success" sx={{ mb: 2 }}>{success}</Alert>}

          <TextField
            margin="normal"
            required
            fullWidth
            id="title"
            label="Plan Title"
            name="title"
            value={plan.title}
            onChange={handlePlanChange}
            disabled={loading}
            autoFocus
          />

          <TextField
            margin="normal"
            fullWidth
            id="description"
            label="Plan Description (Optional)"
            name="description"
            multiline
            rows={4}
            value={plan.description}
            onChange={handlePlanChange}
            disabled={loading}
          />

          <Divider sx={{ my: 3 }}>Exercises</Divider>

          {/* --- Exercise List Section --- */}
          <Box sx={{ mb: 2 }}>
            <Typography variant="h6" gutterBottom>
              Manage Exercises
            </Typography>
              {plan.exercises.length === 0 && (
                <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
                    No exercises added yet.
                </Typography>
              )}
            {/* Map over plan.exercises to render exercise input fields */}
            {plan.exercises.map((exercise: ExerciseInput, index: number) => (
                <Paper key={index} sx={{ p: 2, mb: 2, border: '1px solid #eee' }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid item xs={12} sm={5}>
                            <TextField
                                fullWidth
                                required
                                label={`Exercise ${index + 1}: Title`}
                                value={exercise.title}
                                onChange={(e: React.ChangeEvent<HTMLInputElement>) => handleExerciseChange(index, 'title', e.target.value)}
                                disabled={loading}
                                size="small"
                            />
                        </Grid>
                        <Grid item xs={12} sm={5}>
                            <TextField
                                fullWidth
                                label="Instructions (Optional)"
                                value={exercise.instructions}
                                onChange={(e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => handleExerciseChange(index, 'instructions', e.target.value)}
                                disabled={loading}
                                multiline
                                rows={1} // Keep it compact initially
                                size="small"
                            />
                        </Grid>
                        <Grid item xs={12} sm={2} sx={{ textAlign: 'right' }}>
                          <Typography variant="caption" display="block">Order: {exercise.sequence_order}</Typography>
                          <IconButton
                              aria-label="Remove exercise"
                              onClick={() => removeExercise(index)}
                              disabled={loading}
                              color="error"
                          >
                              <DeleteIcon />
                          </IconButton>
                        </Grid>
                    </Grid>
                     {/* TODO: Add inputs for image/video later */}
                </Paper>
            ))}
          </Box>


          <Button
            variant="outlined"
            startIcon={<AddIcon />}
            onClick={addExercise}
            disabled={loading}
            sx={{ mb: 3 }}
          >
            Add Exercise
          </Button>
          {/* --- End Exercise List Section --- */}


          <Divider sx={{ my: 3 }} />

          <Button
            type="submit"
            variant="contained"
            disabled={loading || !plan.title} // Disable if loading or no title
            sx={{ mt: 1 }}
          >
            {loading ? <CircularProgress size={24} /> : "Create Plan"}
          </Button>
        </Box>
      </Paper>
    </Container>
  );
}

export default TherapyPlanCreatePage;
