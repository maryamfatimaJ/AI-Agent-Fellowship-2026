<h1>Assignment 4: Prompt Engineering Experiments</h1>

<h2>Objective</h2>

<p>
  The objective of this assignment is to explore different prompt engineering
  techniques and observe how changes in a prompt affect the quality, clarity,
  accuracy, and structure of an AI-generated response.
</p>

<h2>Model Used</h2>

<p>
  <strong>Model/Platform:</strong> Chatgpt Plus
</p>



<hr>

<h2>Experiment 1: Role Prompting</h2>

<h3>Goal</h3>

<p>
  To observe how assigning a specific role to the AI model affects its tone,
  explanation style, level of detail, and suitability for a particular audience.
</p>

<h3>Basic Prompt</h3>

<pre><code>Explain machine learning.</code></pre>

<h3>Basic Output</h3>

<blockquote>
At its core, Machine Learning (ML) is a branch of artificial intelligence that allows computers to learn and make decisions without being explicitly programmed for every single scenario.

Instead of writing strict, line-by-line rules (e.g., "If an email contains the word 'Winner', mark it as spam"), you feed a machine learning algorithm a massive amount of data, and it figures out the rules and patterns on its own....
</blockquote>
<p>
  <em>Note: The output has been shortened for readability.</em>
</p>

<h3>Role-Based Prompt</h3>

<pre><code>You are a friendly AI instructor teaching a beginner.

Explain machine learning in simple language.

Requirements:
- Use no more than 150 words.
- Include one real-life example.
- Explain any technical term that you use.
- Avoid unnecessary jargon.</code></pre>

<h3>Role-Based Output</h3>

<blockquote>
  Machine learning is a way of teaching computers to learn from examples instead of giving them fixed instructions for every task.

The computer studies data, which means information such as numbers, pictures, or text. It then finds patterns and uses them to make a prediction, meaning an educated guess about a new situation.

For example, an email app can learn to detect spam. It studies many emails labelled “spam” or “not spam.” It notices patterns, such as suspicious links or repeated words. When a new email arrives, it predicts whether the email is spam.

The set of rules learned by the computer is called a model. A model improves when it is trained using more accurate and useful data.

In simple words, machine learning helps computers learn from past examples and make decisions about new information.
</blockquote>

<h3>Observations</h3>


<p>
In the first prompt, I observed that both models—ChatGPT Plus and Gemini—provided detailed explanations of machine learning. They covered the basic definition, examples, types of machine learning, and a general explanation of how machine learning works. However, the responses were quite lengthy and included more information than was necessary for a beginner.

</p>

<p>
In the second prompt, I added clear instructions, including a 150-word limit, simple language, and one real-life example. As a result, both models produced shorter, more focused, and beginner-friendly responses. The main concepts were explained without unnecessary detail, and the example made the explanation easier to understand.
</p>

<h3>Improvements</h3>

<p>
  The role-based prompt could be improved by making the instructions more professional and flexible. The 150-word limit helped reduce unnecessary detail, but it also restricted the model from explaining some important concepts in greater depth. Instead of using a strict word limit, the prompt could ask for a concise but complete explanation.
</p>

<hr>

<h2>Experiment 2: Step-by-Step Reasoning Prompting</h2>

<h3>Goal</h3>

<p>
  To observe whether asking the model to show clear and verifiable steps makes
  the solution easier to understand and check.
</p>

<h3>Basic Prompt</h3>

<pre><code>A shop gives a 20% discount on a product costing Rs. 5,000.
What is the final price?</code></pre>

<h3>Basic Output</h3>

<blockquote>
 20% of Rs. 5,000 = Rs. 1,000

Final price = Rs. 5,000 − Rs. 1,000 = Rs. 4,000
</blockquote>

<h3>Improved Prompt</h3>

<pre><code>Solve the following problem using brief and verifiable calculation steps.

First calculate the discount amount.
Then subtract it from the original price.
Finally, check the answer once.

Problem:
A shop gives a 20% discount on a product costing Rs. 5,000.
What is the final price?</code></pre>

<h3>Improved Output</h3>

<blockquote>
1. Discount amount
20%×5,000= 10020×5,000=1,000

2. Subtract the discount
5,000−1,000= 4,000

3. Check
The customer pays 80% of the original price:
80%×5,000= 4,000

Final price: Rs. 4,000
</blockquote>

<h3>Observations</h3>

<p> Both prompts produced the correct final answer of Rs. 4,000. The basic prompt already showed the discount calculation and subtraction clearly, so it was sufficient for this simple problem. </p>

<p> The improved prompt produced a more organized response by separating the solution into three parts: calculating the discount, subtracting it from the original price, and checking the result using another method. The final verification made the answer easier to confirm and reduced the possibility of an unnoticed calculation error. </p>

<h3>Improvements</h3>

<p>
No need of improvement in accuracy because both prompts produced the same correct answer. The main difference was the level of detail. The basic prompt was already clear enough for such a simple calculation, while the second prompt added a separate verification step.
</p>

<hr>

<h2>Experiment 3: Few-Shot Prompting</h2>

<h3>Goal</h3>

<p>
  To observe how examples help the model understand the required task, labels,
  and expected output format.
</p>

<h3>Zero-Shot Prompt</h3>

<pre><code>Classify the sentiment of the following sentence as Positive, Negative, or Mixed.

Sentence:
"The app is useful, but it crashes frequently."</code></pre>

<h3>Zero-Shot Output</h3>

<blockquote>
 Mixed

The sentence is positive about the app being useful, but negative about it crashing frequently.
</blockquote>

<h3>Few-Shot Prompt</h3>

<pre><code>Classify each sentence as Positive, Negative, or Mixed.

Example 1:
Input: "The interface is clean and easy to use."
Output: Positive

Example 2:
Input: "The service was slow and disappointing."
Output: Negative

Example 3:
Input: "The design is beautiful, but the app crashes often."
Output: Mixed

Now classify the following sentence.

Input: "The app is useful, but it crashes frequently."

Return only one label:
Positive, Negative, or Mixed.</code></pre>

<h3>Few-Shot Output</h3>

<blockquote>
  Mixed
</blockquote>

<h3>Observations</h3>

<p> Both prompts produced the correct sentiment label, which was "Mixed." In the zero-shot prompt, the model returned the label along with a short explanation because the prompt did not specify that only one label should be returned. </p>

<p> In the few-shot prompt, the examples showed the expected pattern, and the final instruction clearly stated that the model should return only one label. As a result, the response was shorter, more consistent, and followed the required format exactly. </p>

<h3>Improvements</h3>

<p>
  To make the comparison more accurate, both prompts should use the same output instruction. For example, the zero-shot prompt should also ask the model to return only one label. This would help determine whether the examples themselves improve the result.
</p>

<p>
  The few-shot prompt could also include more difficult or ambiguous examples. This would test whether the model can classify sentences where positive and negative meanings are less obvious.
</p>


<hr>

<h2>Experiment 4: Structured Output in JSON</h2>

<h3>Goal</h3>

<p>
  To observe how defining a JSON schema makes the model's response predictable,
  structured, and easier to use inside an application.
</p>

<h3>Basic Prompt</h3>

<pre><code>Extract the student's name, degree, skills, and career goal from this text:

Maryam is a BS Artificial Intelligence student.
She knows Python, SQL, and machine learning.
She wants to become an AI Engineer.</code></pre>

<h3>Basic Output</h3>

<blockquote>
Name: Maryam
Degree: BS Artificial Intelligence
Skills: Python, SQL, Machine Learning
Career Goal: AI Engineer
</blockquote>

<h3>Structured Prompt</h3>

<pre><code>Extract information from the following text.

Return only valid JSON.
Do not include markdown, comments, or additional explanation.

Use this exact schema:

{
  "name": "string or null",
  "degree": "string or null",
  "skills": ["string"],
  "career_goal": "string or null"
}

If any information is missing, use null.

Text:
Maryam is a BS Artificial Intelligence student.
She knows Python, SQL, and machine learning.
She wants to become an AI Engineer.</code></pre>

<h3>Structured Output</h3>

<pre><code>
{
"name": "Maryam",
"degree": "BS Artificial Intelligence",
"skills": ["Python", "SQL", "machine learning"],
"career_goal": "AI Engineer"
}
</code></pre>

<h3>Observations</h3>

<p> Both prompts extracted the correct information. The first prompt returned a readable text response, while the second prompt organized the same information in valid JSON format. The JSON response is more suitable for software applications because each value can be accessed using a specific key. </p>

<h3>Improvements</h3>

<p> The structured prompt could be improved by defining consistent capitalization for skills and by testing missing information to confirm that the model correctly returns <code>null</code> when required. </p>
<hr>

<h2>Experiment 5: Prompt Optimization</h2>

<h3>Goal</h3>

<p>
  To improve a weak and general prompt by adding context, audience, constraints,
  goals, and an expected output format.
</p>

<h3>Prompt Version 1: Weak Prompt</h3>

<pre><code>Make a study plan.</code></pre>

<h3>Output of Version 1</h3>

<blockquote>
  Simple Daily Study Plan

Assuming you can study for about 4 hours daily:

1. AI Engineering — 1 hour 30 minutes
Learn one concept, such as LLMs, prompt engineering, APIs, or AI agents.
Write short notes in your own words.
Practise the concept with a small example.
</blockquote>

<h3>Prompt Version 2: Partially Improved Prompt</h3>

<pre><code>Create a 7-day study plan for learning Python basics.</code></pre>

<h3>Output of Version 2</h3>

<blockquote>
  7-Day Python Basics Study Plan
Day 1: Python Introduction
Install Python and VS Code
Learn print()
Understand variables
Learn basic data types: string, integer, float, and boolean
Practice: Store your name, age, and degree in variables and print them
Day 2: Input and Operators
Learn input()
Convert input using int() and float()
Practice arithmetic operators: +, -, *, /, %
Practice: Create a simple calculator...
</blockquote>

<h3>Prompt Version 3: Optimized Prompt</h3>

<pre><code>Create a realistic 7-day beginner-friendly Python study plan.

Learner context:
- The learner understands very basic programming concepts.
- The learner can study for 90 minutes per day.
- The learner wants to practice instead of memorizing syntax.

Learning goals:
- Variables and data types
- Conditions
- Loops
- Functions
- Lists and dictionaries
- Error handling

Requirements:
- Divide every day into learning, practice, and revision.
- Include one small coding task per day.
- Include a small final project on Day 7.
- Present the response in a markdown table.
- Keep the workload realistic and beginner-friendly.</code></pre>

<h3>Output of Version 3</h3>

<blockquote>
<table border="1" cellpadding="10" cellspacing="0">
  <thead>
    <tr>
      <th>Day</th>
      <th>Learning — 30 min</th>
      <th>Practice — 45 min</th>
      <th>Revision — 15 min</th>
      <th>Small Coding Task</th>
    </tr>
  </thead>

  <tbody>
    <tr>
      <td><strong>Day 1: Variables and Data Types</strong></td>
      <td>
        Learn variables, strings, integers, floats, booleans,
        <code>print()</code>, and <code>input()</code>.
      </td>
      <td>
        Create variables, take user input, and practise simple calculations.
      </td>
      <td>
        Explain each data type in your own words and review your mistakes.
      </td>
      <td>
        Build a personal profile program that displays the user's name,
        age, degree, and favourite subject.
      </td>
    </tr>
  </tbody>
</table>
  
</blockquote>

<h3>Observations</h3>

<p> The optimized prompt produced a more detailed, organized, and practical study plan than the earlier versions. The learner’s experience level, available study time, learning goals, and preferred practice-based approach helped the model create a realistic schedule. Dividing each day into learning, practice, revision, and a coding task also made the plan easier to follow. </p>
<h3>Improvements</h3>

<p> The prompt could be improved further by including the learner’s weak areas, preferred learning resources, and current Python knowledge. It could also ask for a short progress-check activity after every few days so the learner can evaluate understanding before moving forward. </p>

<hr>


<h2>Conclusion</h2>

<p>
  Through these prompt engineering experiments, I learned how strongly the quality of a prompt affects the response of an LLM. Clear role instructions, detailed context, examples, constraints, and structured output requirements helped the models produce more relevant, focused, and useful responses. I also learned that a longer prompt is not always better. The prompt should match the user’s purpose and include only the information needed for the task. Overall, these experiments helped me understand the importance of designing prompts carefully instead of relying on vague instructions.
</p>

