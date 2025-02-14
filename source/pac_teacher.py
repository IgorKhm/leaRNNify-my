import time
from collections import namedtuple

import matplotlib.pyplot as plt
import numpy as np

from dfa import DFA
from dfa_check import DFAChecker
from modelPadding import RNNLanguageClasifier
from random_words import random_word, confidence_interval_many, confidence_interval_many_for_reuse
from teacher import Teacher
from randwords import random_words, is_words_in_dfa,compare_list_of_bool

class PACTeacher(Teacher):

    def __init__(self, model: DFA, epsilon=0.001, delta=0.001):
        assert ((epsilon <= 1) & (delta <= 1))
        Teacher.__init__(self, model)
        self.epsilon = epsilon
        self.delta = delta
        self._log_delta = np.log(delta)
        self._log_one_minus_epsilon = np.log(1 - epsilon)
        self._num_equivalence_asked = 0

        self.prev_examples = {}

        self.is_counter_example_in_batches = isinstance(self.model, RNNLanguageClasifier)
        print("counter example in batchs : " + str(self.is_counter_example_in_batches))
    def equivalence_query(self, dfa: DFA):
        """
        Tests whether the dfa is equivalent to the model by testing random words.
        If not equivalent returns an example
        """


        # if dfa.is_word_in("") != self.model.is_word_in(""):
        #     return ""

        # number_of_rounds0 = int((self._log_delta - self._num_equivalence_asked) / self._log_one_minus_epsilon)
        number_of_rounds = int(
            (1 / self.epsilon) * (np.log(1 / self.delta) + np.log(2) * (self._num_equivalence_asked + 1)))

        self._num_equivalence_asked = self._num_equivalence_asked + 1


        if self.is_counter_example_in_batches:
            batch_size = 200
            for i in range(int(number_of_rounds / batch_size) + 1):
                batch = random_words(batch_size,self.alphabet)
                # batch = [random_word(self.model.alphabet) for _ in range(batch_size)]
                for x, y, w in zip(self.model.is_words_in_batch(batch) > 0.5, is_words_in_dfa(dfa,batch),
                                   batch):
                    if x != y:
                        return w
            return None

        else:
            for i in range(number_of_rounds):
                word = random_word(self.model.alphabet)
                if self.model.is_word_in(word) != dfa.is_word_in(word):
                    return word
            return None

    def model_subset_of_dfa_query(self, dfa: DFA):
        """
        Tests whether the model language is a subset of the dfa language by testing random words.
        If not subset returns an example
        """

        # if dfa.is_word_in("") != self.model.is_word_in(""):
        #     return ""

        # number_of_rounds0 = int((self._log_delta - self._num_equivalence_asked) / self._log_one_minus_epsilon)
        number_of_rounds = int(
            (1 / self.epsilon) * (np.log(1 / self.delta) + np.log(2) * (self._num_equivalence_asked + 1)))
        self._num_equivalence_asked = self._num_equivalence_asked + 1

        #print("num_rounds")
        #print(number_of_rounds)
        # print(number_of_rounds0)

        if isinstance(self.model, RNNLanguageClasifier):
            batch_size = 200
            for i in range(int(number_of_rounds / batch_size) + 1):
                batch = [random_word(self.model.alphabet) for _ in range(batch_size)]
                for x, y, w in zip(self.model.is_words_in_batch(batch) > 0.5, [dfa.is_word_in(w) for w in batch],
                                   batch):
                    if x and (not y):
                        return w
            return None

        else:
            for i in range(number_of_rounds):
                word = random_word(self.model.alphabet)
                if self.model.is_word_in(word) != dfa.is_word_in(word):
                    return word
            return None

    def membership_query(self, word):
        return self.model.is_word_in(word)

    def teach(self, learner, timeout=600):
        self._num_equivalence_asked = 0
        learner.teacher = self
        i = 0
        start_time = time.time()
        t100 = start_time
        while True:
            if self._num_equivalence_asked > timeout:
                print(time.time() - start_time)
                return
            # print(i)
            i = i + 1
            if i % 100 == 0:
                print("this is the {}th round".format(i))
                print("{} time has passed from the begging and {} from the last 100".format(time.time() - start_time,
                                                                                            time.time() - t100))
                t100 = time.time()

            counter = self.equivalence_query(learner.dfa)
            if counter is None:
                break
            num_of_ref = learner.new_counterexample(counter, self.is_counter_example_in_batches)
            self._num_equivalence_asked += num_of_ref

    def teach_and_trace(self, student, dfa_model, timeout=900):
        output, smaples, answers = confidence_interval_many_for_reuse([dfa_model, self.model, student.dfa], random_word,
                                                                      width=0.005, confidence=0.005)
        dist_to_dfa_vs = []
        dist_to_rnn_vs = []
        num_of_states = []

        # points.append(DataPoint(len(student.dfa.states), output[0, 2], output[1, 2]))

        a = None
        student.teacher = self
        i = 0
        start_time = time.time()
        t100 = start_time
        while True:
            if time.time() - start_time > timeout:
                break
            i = i + 1
            if i % 100 == 0:
                print("this is the {}th round".format(i))
                print("{} time has passed from the begging and {} from the last 100".format(time.time() - start_time,
                                                                                            time.time() - t100))
                t100 = time.time()
            counter = self.equivalence_query(student.dfa)
            if counter is None:
                break
            student.new_counterexample(counter, do_hypothesis_in_batches=False)

            print('compute dist')
            output, _, answers = confidence_interval_many_for_reuse([dfa_model, self.model, student.dfa], random_word,
                                                                    answers, samples=smaples, width=0.1, confidence=0.1)
            # points.append(DataPoint(len(student.dfa.states), output[0, 2], output[1, 2]))

            dist_to_dfa_vs.append(output[0][2])
            dist_to_rnn_vs.append(output[1][2])
            num_of_states.append(len(student.dfa.states))
            print('done compute dist')

        # plt.plot(num_of_states, dist_to_dfa_vs, label="DvD",color='green', linestyle='dashed')
        # plt.title('original dfa vs extracted dfa')
        #
        # plt.plot(num_of_states, dist_to_rnn_vs, label="RvD",)
        # plt.title('rnn vs extracted dfa')
        # plt.legend()
        # plt.figure()

        #
        fig = plt.figure(dpi=1200)
        ax = fig.add_subplot(2, 1, 1)

        ax.plot(num_of_states, dist_to_dfa_vs, color='blue', lw=2)

        ax.set_yscale('log')

        plt.show()

    # def check_and_teach(self, learner, checkers: [DFAChecker], timeout=900):
    #     learner.teacher = self
    #     self._num_equivalence_asked = 0
    #     start_time = time.time()
    #     Counter_example = namedtuple('Counter_example', ['word', 'is_super'])
    #
    #     while True:
    #         if time.time() - start_time > timeout:
    #             return
    #         print(time.time() - start_time)
    #
    #         counter_example = Counter_example(None, None)
    #
    #         # Searching for counter examples in the spec:
    #         counters_examples = (Counter_example(checker.check_for_counterexample(learner.dfa), checker.is_super_set)
    #                              for checker in checkers)
    #         for example in counters_examples:
    #             if example.word is not None:
    #                 counter_example = example
    #                 break
    #         if counter_example.word is not None:
    #             if counter_example.is_super != (self.model.is_word_in(counter_example.word)):
    #                 self._num_equivalence_asked += 1
    #                 num = learner.new_counterexample(counter_example[0], self.is_counter_example_in_batches)
    #                 if num > 1:
    #                     self._num_equivalence_asked += num - 1
    #             else:
    #                 print('found counter mistake in the model: ', counter_example)
    #                 return counter_example
    #
    #         # Searching for counter examples in the the model:
    #         else:
    #
    #             counter_example = self.model_subset_of_dfa_query(learner.dfa)
    #             if counter_example is None:
    #                 return None
    #             else:
    #                 num = learner.new_counterexample(counter_example, self.is_counter_example_in_batches)
    #                 if num > 1:
    #                     self._num_equivalence_asked += num - 1
    def check_and_teach(self, learner, checker, timeout=600):
        learner.teacher = self
        self._num_equivalence_asked = 0
        start_time = time.time()


        while True:
            if time.time() - start_time > timeout:
                return



            counter_example = None
            # Searching for counter examples in the spec:
            counter_example = checker.check_for_counterexample(learner.dfa)

            if counter_example is not None:
                if not self.model.is_word_in(counter_example):
                    self._num_equivalence_asked += 1
                    num = learner.new_counterexample(counter_example, self.is_counter_example_in_batches)
                    if num > 1:
                        self._num_equivalence_asked += num - 1
                else:
                    print('found counter mistake in the model: ', counter_example)
                    return counter_example

            # Searching for counter examples in the the model:
            else:

                counter_example = self.model_subset_of_dfa_query(learner.dfa)
                if counter_example is None:
                    return None
                else:
                    # if not checker.specification.is_word_in(counter_example):
                    #     num = learner.new_counterexample(counter_example, self.is_counter_example_in_batches,max_refinements = len(counter_example)*100)
                    #     print("rand mistake")
                    #     print(checker.specification.is_word_in(counter_example))
                    #     print(learner.dfa.is_word_in(counter_example))
                    #     print(self.membership_query(counter_example))
                    # else:
                    num = learner.new_counterexample(counter_example, self.is_counter_example_in_batches)
                    if num > 1:
                        self._num_equivalence_asked += num - 1

    def teach_a_superset(self, learner, timeout=900):
        self._num_equivalence_asked = 0
        learner.teacher = self
        i = 0
        start_time = time.time()
        t100 = start_time
        while True:
            if time.time() - start_time > timeout:
                print(time.time() - start_time)
                return
            # print(i)
            i = i + 1
            if i % 100 == 0:
                print("this is the {}th round".format(i))
                print("{} time has passed from the begging and {} from the last 100".format(time.time() - start_time,
                                                                                            time.time() - t100))
                t100 = time.time()

            counter = self.model_subset_of_dfa_query(learner.dfa)
            if counter is None:
                break
            learner.new_counterexample(counter, self.is_counter_example_in_batches)
